Title: Fix Application publication order during base context attachment

AnkiDroid 2.26.0alpha6 can capture its own Application as the base of its profile context wrapper during `Application.attachBaseContext`. Once the Application delegates preference access to that wrapper, `getSharedPreferences` recurses between the two until a StackOverflowError.

Move `ContextImpl.setApplication(app)` after `app.huskAttach(base)`. The base context then supplies its pre-publication fallback during attachment, and the Application remains available to content providers and `onCreate` after attachment completes.

Validation:

- Compiled all 3,084 Java framework/stub source files with Eclipse ECJ 3.39.0 using Java 8 source/target settings; generated 5,797 framework class files with no compiler diagnostics. This is a host compilation check, not the repository's javac/D8 or Xcode build.
- Ran a host probe against the real compiled Husk `ContextImpl`, `Application`, and `ContextWrapper` classes. Original ordering captures the Application in its own wrapper; corrected ordering captures the base and exposes the Application after attachment. The probe isolates attach semantics and does not execute `AppRunner.run`, ART, or native iOS code.
- Confirmed the official Husk 3.0.0 build 129 framework contains the original adjacent calls. Prepared an experimental IPA with only those two DEX instructions exchanged, refreshed DEX integrity fields, and a local build label. Reparsed the patched DEX and verified IPA ZIP integrity and unchanged retained entries. Re-signing and device testing remain required.

AnkiWeb login and the note-editor freeze are separate unresolved symptoms. This change does not claim to fix either. No iPad runtime validation or native iOS rebuild was possible in the Linux environment.
