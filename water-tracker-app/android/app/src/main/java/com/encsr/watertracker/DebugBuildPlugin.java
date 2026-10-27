package com.encsr.watertracker;

import android.webkit.WebView;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import com.getcapacitor.Plugin;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.util.Collections;

/**
 * Registered from MainActivity ONLY when BuildConfig.DEBUG (mirrors iOS #if DEBUG WTBridgeViewController).
 * Plugin.load() runs during Bridge setup, before the first page load, so the document-start
 * script is in place before index.html's scripts run.
 */
@CapacitorPlugin(name = "WTDebugBuild")
public class DebugBuildPlugin extends Plugin {
    static final String JS = "window.__WT_DEBUG_BUILD__ = true;";

    @Override
    public void load() {
        if (!BuildConfig.DEBUG) return; // belt and braces
        WebView.setWebContentsDebuggingEnabled(true); // chrome://inspect
        WebView wv = getBridge().getWebView();
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            WebViewCompat.addDocumentStartJavaScript(wv, JS, Collections.singleton("*"));
        } else {
            // Old WebView fallback: set the flag as soon as possible; the page re-checks it lazily.
            wv.post(() -> wv.evaluateJavascript(JS, null));
        }
    }

    @Override
    protected void handleOnResume() {
        if (!BuildConfig.DEBUG) return;
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            WebView wv = getBridge().getWebView();
            wv.post(() -> wv.evaluateJavascript(JS, null));
        }
    }
}
