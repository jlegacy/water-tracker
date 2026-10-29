package com.encsr.watertracker;

import android.os.Bundle;
import android.view.View;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
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

        // The padded strips behind the status bar and nav bar show the container's
        // background. Paint them the app's dark navy (#0b1d33, same as the web body)
        // and use light (white) system icons so the nav buttons aren't white-on-white.
        container.setBackgroundColor(0xFF0B1D33);
        applyLightSystemBarIcons();
    }

    @Override
    public void onResume() {
        super.onResume();
        // Capacitor/theme can reset the bar icon colors after onCreate, so re-apply
        // now and once more after the first layout pass.
        applyLightSystemBarIcons();
        getWindow().getDecorView().post(this::applyLightSystemBarIcons);
    }

    private void applyLightSystemBarIcons() {
        WindowInsetsControllerCompat bars =
            WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        bars.setAppearanceLightStatusBars(false);   // white clock/battery icons
        bars.setAppearanceLightNavigationBars(false); // white nav buttons
    }
}
