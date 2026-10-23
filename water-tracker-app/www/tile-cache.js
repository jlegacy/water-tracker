/**
 * On-demand OSM map tile cache for Leaflet (caches tiles the rider already viewed).
 * IndexedDB + LRU-by-lastAccess eviction. No pre-built MBTiles / region packs.
 *
 * Cap: TILE_CACHE_MAX_BYTES (~75 MB). Online: CORS fetch → cache blob → display;
 * if CORS/network blocks reading bytes, falls back to normal img.src (no cache write).
 * Offline / fetch fail: serve from IndexedDB when present.
 */
(function (global) {
  'use strict';
  if (typeof L === 'undefined') return;

  var TILE_CACHE_DB_NAME = 'water-tracker-tiles';
  var TILE_CACHE_STORE = 'tiles';
  /** Soft cap for cached tile blobs; oldest-by-lastAccess evicted first. */
  var TILE_CACHE_MAX_BYTES = 75 * 1024 * 1024; // ~75 MB

  var dbPromise = null;
  var pruneScheduled = false;
  // tile img element → object URL (for revokeObjectURL)
  var objectUrls = typeof WeakMap !== 'undefined' ? new WeakMap() : null;
  var objectUrlsFallback = objectUrls ? null : [];

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise(function (resolve, reject) {
      if (!global.indexedDB) {
        reject(new Error('no IndexedDB'));
        return;
      }
      var req = indexedDB.open(TILE_CACHE_DB_NAME, 1);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(TILE_CACHE_STORE)) {
          var store = db.createObjectStore(TILE_CACHE_STORE, { keyPath: 'key' });
          store.createIndex('lastAccess', 'lastAccess', { unique: false });
        }
      };
      req.onsuccess = function () {
        resolve(req.result);
      };
      req.onerror = function () {
        reject(req.error || new Error('idb open failed'));
      };
    });
    return dbPromise;
  }

  function tileKey(coords) {
    return coords.z + '/' + coords.x + '/' + coords.y;
  }

  function getCached(key) {
    return openDb()
      .then(function (db) {
        return new Promise(function (resolve, reject) {
          var tx = db.transaction(TILE_CACHE_STORE, 'readwrite');
          var store = tx.objectStore(TILE_CACHE_STORE);
          var g = store.get(key);
          g.onsuccess = function () {
            var row = g.result;
            if (row && row.blob) {
              row.lastAccess = Date.now();
              store.put(row);
              resolve(row);
            } else {
              resolve(null);
            }
          };
          g.onerror = function () {
            reject(g.error);
          };
        });
      })
      .catch(function () {
        return null;
      });
  }

  function putCached(key, blob) {
    if (!blob || !blob.size) return Promise.resolve();
    return openDb()
      .then(function (db) {
        return new Promise(function (resolve, reject) {
          var tx = db.transaction(TILE_CACHE_STORE, 'readwrite');
          tx.objectStore(TILE_CACHE_STORE).put({
            key: key,
            blob: blob,
            bytes: blob.size,
            lastAccess: Date.now()
          });
          tx.oncomplete = function () {
            resolve();
            schedulePrune();
          };
          tx.onerror = function () {
            reject(tx.error);
          };
        });
      })
      .catch(function () {});
  }

  function schedulePrune() {
    if (pruneScheduled) return;
    pruneScheduled = true;
    setTimeout(function () {
      pruneScheduled = false;
      pruneToCap();
    }, 400);
  }

  function pruneToCap() {
    openDb()
      .then(function (db) {
        return new Promise(function (resolve, reject) {
          var tx = db.transaction(TILE_CACHE_STORE, 'readonly');
          var req = tx.objectStore(TILE_CACHE_STORE).getAll();
          req.onsuccess = function () {
            resolve({ db: db, rows: req.result || [] });
          };
          req.onerror = function () {
            reject(req.error);
          };
        });
      })
      .then(function (pack) {
        var db = pack.db;
        var rows = pack.rows;
        var total = 0;
        for (var i = 0; i < rows.length; i++) total += rows[i].bytes || 0;
        if (total <= TILE_CACHE_MAX_BYTES) return;
        rows.sort(function (a, b) {
          return (a.lastAccess || 0) - (b.lastAccess || 0);
        });
        var toDelete = [];
        for (var j = 0; j < rows.length && total > TILE_CACHE_MAX_BYTES; j++) {
          toDelete.push(rows[j].key);
          total -= rows[j].bytes || 0;
        }
        if (!toDelete.length) return;
        return new Promise(function (resolve, reject) {
          var tx = db.transaction(TILE_CACHE_STORE, 'readwrite');
          var store = tx.objectStore(TILE_CACHE_STORE);
          for (var k = 0; k < toDelete.length; k++) store.delete(toDelete[k]);
          tx.oncomplete = function () {
            resolve();
          };
          tx.onerror = function () {
            reject(tx.error);
          };
        });
      })
      .catch(function () {});
  }

  function rememberObjectUrl(tile, url) {
    if (objectUrls) {
      objectUrls.set(tile, url);
    } else {
      objectUrlsFallback.push({ tile: tile, url: url });
    }
  }

  function takeObjectUrl(tile) {
    if (objectUrls) {
      var u = objectUrls.get(tile);
      if (u) objectUrls.delete(tile);
      return u || null;
    }
    for (var i = 0; i < objectUrlsFallback.length; i++) {
      if (objectUrlsFallback[i].tile === tile) {
        var url = objectUrlsFallback[i].url;
        objectUrlsFallback.splice(i, 1);
        return url;
      }
    }
    return null;
  }

  function revokeTileUrl(tile) {
    if (!tile) return;
    var u = takeObjectUrl(tile);
    if (u) {
      try {
        URL.revokeObjectURL(u);
      } catch (e) {}
    }
  }

  function setTileBlob(tile, blob, assign) {
    revokeTileUrl(tile);
    var url = URL.createObjectURL(blob);
    rememberObjectUrl(tile, url);
    assign(url);
  }

  var CachedTileLayer = L.TileLayer.extend({
    createTile: function (coords, done) {
      var self = this;
      var tile = document.createElement('img');
      tile.alt = '';
      tile.setAttribute('role', 'presentation');

      var url = this.getTileUrl(coords);
      var key = tileKey(coords);
      var bound = false;

      // Bind load/error only when a real src is assigned, so an empty-src
      // error can't mark the tile failed before async cache/fetch finishes.
      function assign(src) {
        if (!bound) {
          bound = true;
          L.DomEvent.on(tile, 'load', L.Util.bind(self._tileOnLoad, self, done, tile));
          L.DomEvent.on(tile, 'error', L.Util.bind(self._tileOnError, self, done, tile));
        }
        tile.src = src;
      }

      getCached(key).then(function (row) {
        if (row && row.blob) {
          setTileBlob(tile, row.blob, assign);
          return;
        }
        if (typeof fetch !== 'function') {
          assign(url);
          return;
        }
        fetch(url, { mode: 'cors', credentials: 'omit' })
          .then(function (res) {
            if (!res.ok) throw new Error('tile http ' + res.status);
            return res.blob();
          })
          .then(function (blob) {
            if (!blob || !blob.size) throw new Error('empty tile');
            setTileBlob(tile, blob, assign);
            putCached(key, blob);
          })
          .catch(function () {
            // CORS/network fail: plain img request (no cache write, no crossOrigin).
            assign(url);
          });
      });

      return tile;
    },

    _removeTile: function (key) {
      var tile = this._tiles[key] && this._tiles[key].el;
      if (tile) revokeTileUrl(tile);
      return L.TileLayer.prototype._removeTile.call(this, key);
    }
  });

  L.TileLayer.Cached = CachedTileLayer;
  L.tileLayer.cached = function (urlTemplate, options) {
    return new CachedTileLayer(urlTemplate, options);
  };

  global.TILE_CACHE_MAX_BYTES = TILE_CACHE_MAX_BYTES;
})(typeof window !== 'undefined' ? window : this);
