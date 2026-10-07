import { test } from "node:test";
import assert from "node:assert/strict";
import { getRedemptionEndpoints, requestRecyclingReward, REDEMPTION_UNAVAILABLE } from "./recyclingRedemption.js";
import { getTrustedTunnelUrl } from "./qrCodes.js";

const oldUrl = "https://old.trycloudflare.com";
const currentUrl = "https://current.trycloudflare.com";
const success = () => Response.json({ ok: true, pointsEarned: 0.5, totalPoints: 1.5 });

test("rewards created before the tunnel starts use current machine discovery", () => {
  assert.deepEqual(getRedemptionEndpoints({
    reward: { machineId: "one", redemptionApiUrl: null },
    machine: { redemptionApiUrl: currentUrl },
  }), [currentUrl]);
});

test("current discovery precedes stale reward URLs and ignores another machine", () => {
  assert.deepEqual(getRedemptionEndpoints({
    reward: { machineId: "one", redemptionApiUrl: oldUrl },
    legacyEndpoint: { machineId: "one", url: currentUrl },
  }), [currentUrl, oldUrl]);
  assert.deepEqual(getRedemptionEndpoints({
    reward: { machineId: "one", redemptionApiUrl: oldUrl },
    legacyEndpoint: { machineId: "two", url: currentUrl },
  }), [oldUrl]);
  assert.deepEqual(getRedemptionEndpoints({ reward: {} }), []);
});

test("explicit public configuration takes precedence and duplicate endpoints are removed", () => {
  assert.deepEqual(getRedemptionEndpoints({
    reward: { machineId: "one", redemptionApiUrl: oldUrl },
    machine: { redemptionApiUrl: oldUrl },
    configuredUrl: "https://rewards.example/",
    localUrl: "http://192.168.1.2:5000/",
  }), ["https://rewards.example", oldUrl, "http://192.168.1.2:5000"]);
});

test("discovered URLs cannot redirect ID tokens to untrusted destinations", () => {
  for (const url of ["https://evil.example", "http://old.trycloudflare.com",
    "https://old.trycloudflare.com.evil.example", "https://user@old.trycloudflare.com",
    "https://old.trycloudflare.com/path", "https://old.trycloudflare.com/?token=1",
    "https://old.trycloudflare.com:8443", "https://old.trycloudflare.com/#hash"]) {
    assert.equal(getTrustedTunnelUrl(url), "");
  }
});

test("network errors and Cloudflare HTML outages fall back to a reachable endpoint", async () => {
  for (const failure of [() => { throw new TypeError("Load failed"); },
    () => new Response("<html>Bad Gateway</html>", { status: 502 })]) {
    const calls = [];
    const result = await requestRecyclingReward({
      endpoints: [oldUrl, currentUrl], code: "ecorefill://claim/reward", idToken: "token",
      fetchImpl: async (url, options) => {
        calls.push(url);
        assert.equal(options.headers.Authorization, "Bearer token");
        assert.equal(options.redirect, "error");
        return calls.length === 1 ? failure() : success();
      },
    });
    assert.equal(result.pointsEarned, 0.5);
    assert.deepEqual(calls, [oldUrl, currentUrl].map((url) => `${url}/api/recycling/redeem`));
  }
});

test("a stalled request times out and tries the next endpoint", async () => {
  let calls = 0;
  const result = await requestRecyclingReward({
    endpoints: [oldUrl, currentUrl], code: "code", idToken: "token", timeoutMs: 5,
    fetchImpl: async (_url, { signal }) => {
      if (++calls === 2) return success();
      return new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(signal.reason)));
    },
  });
  assert.equal(result.totalPoints, 1.5);
  assert.equal(calls, 2);
});

test("expired, claimed and unauthorized rewards stop without submitting elsewhere", async () => {
  for (const [status, message] of [[400, "This recycling QR code has expired."],
    [400, "You already claimed this recycling reward."], [401, "Please sign in."]]) {
    let calls = 0;
    await assert.rejects(requestRecyclingReward({
      endpoints: [oldUrl, currentUrl], code: "code", idToken: "token",
      fetchImpl: async () => { calls++; return Response.json({ ok: false, message }, { status }); },
    }), { message });
    assert.equal(calls, 1);
  }
});

test("missing discovery and total outages give an actionable retry message", async () => {
  for (const endpoints of [[], [oldUrl]]) {
    await assert.rejects(requestRecyclingReward({
      endpoints, code: "code", idToken: "token",
      fetchImpl: async () => { throw new TypeError("Failed to fetch"); },
    }), { message: REDEMPTION_UNAVAILABLE });
  }
});
