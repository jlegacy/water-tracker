package com.encsr.watertracker;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // DEBUG builds only: DebugBuildPlugin injects window.__WT_DEBUG_BUILD__ so the
        // web Premium dev overrides work. Release builds never register it (stay locked).
        if (BuildConfig.DEBUG) registerPlugin(DebugBuildPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
