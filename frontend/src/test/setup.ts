import '@testing-library/jest-dom/vitest'

// jsdom does not implement the native dialog top layer. Browser checks cover focus/inert/Escape.
if (!HTMLDialogElement.prototype.showModal) HTMLDialogElement.prototype.showModal = function () { this.open = true }
if (!HTMLDialogElement.prototype.close) HTMLDialogElement.prototype.close = function () { this.open = false }
