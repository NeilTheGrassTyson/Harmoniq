// jsdom implements no CSSOM view module, so window.matchMedia is simply absent.
// Components that ask the browser about a breakpoint (AppShell mirrors the
// sidebar's CSS breakpoint to keep aria-expanded honest) would otherwise throw
// on mount. Defaults to matching, i.e. the desktop side of every query, which
// is the layout the existing component tests assume.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string): MediaQueryList => {
    const list: MediaQueryList = {
      matches: true,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
      // Deprecated pair, still referenced by some libraries.
      addListener: () => {},
      removeListener: () => {},
    };
    return list;
  };
}

export {};
