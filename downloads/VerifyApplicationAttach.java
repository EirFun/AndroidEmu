import android.app.Application;
import android.content.Context;
import android.content.ContextWrapper;
import husk.ContextImpl;
import sun.misc.Unsafe;
import java.lang.reflect.Field;

/** Host probe using the real compiled Husk context and Application classes.
 * Isolates wrapper capture at attach time; does not boot ART or call AppRunner.run.
 */
public final class VerifyApplicationAttach {
    private static final class ProfiledApplication extends Application {
        ContextWrapper profile;
        @Override protected void attachBaseContext(Context base) {
            super.attachBaseContext(base);
            Context application = base.getApplicationContext();
            profile = new ContextWrapper(application != null ? application : base);
        }
    }

    public static void main(String[] args) throws Exception {
        Field field = Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        Unsafe unsafe = (Unsafe) field.get(null);
        // Bypass native-backed directory/resource initialization: only the actual
        // getApplicationContext implementation is exercised on the base context.
        ContextImpl base = (ContextImpl) unsafe.allocateInstance(ContextImpl.class);

        ContextImpl.setApplication(null);
        ProfiledApplication legacy = new ProfiledApplication();
        ContextImpl.setApplication(legacy);
        legacy.huskAttach(base);
        if (legacy.profile.getBaseContext() != legacy)
            throw new AssertionError("Original ordering did not reproduce self-delegating capture");
        System.out.println("PASS: original ordering captures the Application in its own profile wrapper");

        ContextImpl.setApplication(null);
        ProfiledApplication fixed = new ProfiledApplication();
        fixed.huskAttach(base);
        ContextImpl.setApplication(fixed);
        if (fixed.profile.getBaseContext() != base)
            throw new AssertionError("Fixed ordering must capture the base context");
        if (base.getApplicationContext() != fixed)
            throw new AssertionError("Application must be available after attach");
        System.out.println("PASS: fixed ordering captures the base and publishes the Application after attach");
        ContextImpl.setApplication(null);
    }
}
