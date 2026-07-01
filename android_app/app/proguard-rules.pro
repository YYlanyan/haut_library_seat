# R8/ProGuard can slow reverse engineering, but cannot make an APK impossible to inspect.
# Keep secrets out of the APK. Store account data in Android Keystore-backed encrypted storage.

-optimizationpasses 5
-allowaccessmodification
-overloadaggressively
-repackageclasses "x"
-flattenpackagehierarchy "x"

# Remove Android log calls from release builds where possible.
-assumenosideeffects class android.util.Log {
    public static int v(...);
    public static int d(...);
    public static int i(...);
}

# Keep Android framework entry points stable.
-keep public class * extends android.app.Activity
-keepclassmembers class * {
    public void *(android.view.View);
}

# Keep JSON model field names only where reflection is used. This project uses manual JSON parsing,
# so no model keep rule is required.
