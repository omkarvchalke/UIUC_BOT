import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement matchMedia -- stub it so components that check
// media features (e.g. ChatInput's touch-device check, next-themes' system
// theme detection) don't crash under test. Defaults to "no match" (desktop,
// fine pointer, light scheme); individual tests can override via
// vi.stubGlobal if they need a specific query to match.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  configurable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// jsdom has no layout engine, so it doesn't implement scrollIntoView --
// stub it as a no-op for components (e.g. ChatWindow) that call it to
// auto-scroll to the latest message.
Element.prototype.scrollIntoView = () => {};
