import { registerPlugin } from '@capacitor/core';
const NativePurchases = registerPlugin('NativePurchases', {
    web: () => import('./web').then((m) => new m.NativePurchasesWeb()),
});
export * from './definitions';
export { NativePurchases };
//# sourceMappingURL=index.js.map