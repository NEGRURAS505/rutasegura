import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'org.rutasegura.carmen',
  appName: 'Amor X Carmen Movi App',
  webDir: 'www',
  android: {
    useLegacyBridge: true,
  },
  plugins: {
    CapacitorHttp: {
      enabled: true,
    },
  },
};

export default config;
