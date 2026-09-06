import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validatePaymentEndpoint } from './paymentEndpoint.js';

test('discovery accepts an HTTPS Quick Tunnel origin', () => {
  assert.equal(validatePaymentEndpoint('https://my-pi.trycloudflare.com/'), 'https://my-pi.trycloudflare.com');
});

test('discovery rejects arbitrary hosts, credentials, paths and deceptive URLs', () => {
  for (const url of [undefined, '', 'http://my-pi.trycloudflare.com', 'https://evil.example',
    'https://my-pi.trycloudflare.com.evil.example', 'https://evil.example@my-pi.trycloudflare.com',
    'https://my-pi.trycloudflare.com/api', 'https://my-pi.trycloudflare.com/?token=1',
    'https://my-pi.trycloudflare.com/#fragment']) {
    assert.throws(() => validatePaymentEndpoint(url));
  }
});

test('explicit configuration supports fixed HTTPS and development-only HTTP', () => {
  assert.equal(validatePaymentEndpoint('https://payments.example', { configured: true }), 'https://payments.example');
  assert.equal(validatePaymentEndpoint('http://192.168.1.2:5000', { configured: true, development: true }), 'http://192.168.1.2:5000');
  assert.throws(() => validatePaymentEndpoint('http://192.168.1.2:5000', { configured: true }));
});
