// Jest DOM polyfills for jsdom
// TextEncoder/TextDecoder are needed by some dependencies
import { TextEncoder, TextDecoder } from "util";

globalThis.TextEncoder = TextEncoder as typeof globalThis.TextEncoder;
globalThis.TextDecoder = TextDecoder as typeof globalThis.TextDecoder;
