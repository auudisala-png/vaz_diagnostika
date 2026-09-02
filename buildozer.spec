[app]
title = VazDiagnostika
package.name = vazdiagnostika
package.domain = org.salim
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3,kivy,jnius
orientation = portrait
fullscreen = 0

[android]
android.api = 33
android.minapi = 21
android.ndk = 25b
android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_SCAN, BLUETOOTH_CONNECT, ACCESS_FINE_LOCATION
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1