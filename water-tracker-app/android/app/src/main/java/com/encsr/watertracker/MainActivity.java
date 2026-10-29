package com.encsr.watertracker;

import android.os.Bundle;
import android.view.View;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // DEBUG builds only: DebugBuildPlugin injects window.__WT_DEBUG_BUILD__ so the
        // web Premium dev overrides work. Release builds never register it (stay locked).
        if (BuildConfig.DEBUG) registerPlugin(DebugBuildPlugin.class);
        super.onCreate(savedInstanceState);

        // Android 15+ (target SDK 35+) forces edge-to-edge, so the web view drew under the
        // status bar and nav bar. Pad the web view's container by the system bar and
        // display-cutout insets so the header sits below the clock/battery icons.
        View webView = getBridge().getWebView();
        View container = (View) webView.getParent();
        ViewCompat.setOnApplyWindowInsetsListener(container, (v, windowInsets) -> {
            Insets bars = windowInsets.getInsets(
                WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return WindowInsetsCompat.CONSUMED;
        });
        ViewCompat.requestApplyInsets(container);
    }
}
