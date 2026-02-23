let syncOutputHandler = () => {};

export function setSyncOutputHandler(handler) {
  syncOutputHandler = typeof handler === 'function' ? handler : () => {};
}

export function syncOutput() {
  syncOutputHandler();
}
