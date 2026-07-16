import "@testing-library/jest-dom";

// Polyfill scrollIntoView for jsdom
Element.prototype.scrollIntoView = jest.fn() as unknown as typeof Element.prototype.scrollIntoView;