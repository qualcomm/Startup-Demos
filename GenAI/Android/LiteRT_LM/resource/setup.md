# LiteRT-LM Android App Setup

Use these steps to recreate the app from the shared `source/` folder.

Shared content:

- `source/AndroidManifest.xml`
- `source/kotlin/`
- `source/layout/`
- `source/values/`
- `instructions.md`

## 1. Create the project

Create a new Android Studio project with:

- Template: `Empty Activity`
- Language: `Kotlin`
- Minimum SDK: `24` or higher
- package name: com.example.litertlm

Follow [Empty Activity project setup instructions](../../../../Tools/Software/Android/empty_activity_project_Init/README.md)

## 2. Copy the shared files


### 2.1 Copy AndroidManifest file from `source/AndroidManifest.xml` into:

```text
app/src/main/AndroidManifest.xml
```

### 2.2 Copy Kotlin files from `source/kotlin/` into:

```text
app/src/main/java/com/example/litertlm/
```

### 2.3 Copy layout files from `source/layout/` into:

```text
app/src/main/res/layout/
```

### 2.4 Copy values files from `source/values/` into:

```text
app/src/main/res/values/
```

Do not replace the whole `values/` folder. Just add these files to the existing folder.

## 3. Update Gradle

Add to `[versions]` in `gradle/libs.versions.toml`:

```toml
recyclerview = "1.3.2"
appcompat = "1.7.0"
litertlm = "latest.release"
```

Add to `[libraries]` in `gradle/libs.versions.toml`:

```toml
androidx-recyclerview = { group = "androidx.recyclerview", name = "recyclerview", version.ref = "recyclerview" }
androidx-appcompat = { group = "androidx.appcompat", name = "appcompat", version.ref = "appcompat" }
google-ai-edge-litertlm-android = { group = "com.google.ai.edge.litertlm", name = "litertlm-android", version.ref = "litertlm" }
```

Add to `dependencies` in `app/build.gradle.kts`:

```kotlin
implementation(libs.androidx.recyclerview)
implementation(libs.androidx.appcompat)
implementation(libs.google.ai.edge.litertlm.android)
```

## 4. Build and run

- Run the app on a device or emulator.
- Note: If the Run button stays disabled, restart Android Studio.

