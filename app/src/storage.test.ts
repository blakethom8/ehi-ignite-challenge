import { beforeEach, describe, expect, it } from "vitest";
import {
  migrateLegacyKey,
  purgeNamespacesByPrefix,
  purgeWorkspaceState,
  storageNamespace,
} from "./storage";

describe("storage namespace helpers", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("encodes one prefix per mode", () => {
    expect(storageNamespace("anonymous", null, "caspian")).toBe(
      "atlas:anon:caspian",
    );
    expect(storageNamespace("demo", "demo-high-risk", "caspian")).toBe(
      "atlas:demo:demo-high-risk:caspian",
    );
    expect(storageNamespace("authenticated", "user_1", "caspian")).toBe(
      "atlas:auth:user_1:caspian",
    );
    expect(storageNamespace("guest", "guest_run_xyz", "caspian")).toBe(
      "atlas:guest:guest_run_xyz:caspian",
    );
  });

  it("purgeNamespacesByPrefix only removes matching keys", () => {
    window.localStorage.setItem("atlas:demo:abc:caspian", "x");
    window.localStorage.setItem("atlas:auth:u1:caspian", "y");
    window.localStorage.setItem("atlas:anon:caspian", "z");
    purgeNamespacesByPrefix("atlas:demo:");
    expect(window.localStorage.getItem("atlas:demo:abc:caspian")).toBeNull();
    expect(window.localStorage.getItem("atlas:auth:u1:caspian")).toBe("y");
    expect(window.localStorage.getItem("atlas:anon:caspian")).toBe("z");
  });

  it("purgeWorkspaceState wipes demo + guest + legacy keys but leaves auth + anon untouched", () => {
    window.localStorage.setItem("atlas:demo:abc:caspian", "demo-state");
    window.localStorage.setItem("atlas:guest:gxyz:caspian", "guest-state");
    window.localStorage.setItem("atlas:auth:u1:caspian", "auth-state");
    window.localStorage.setItem("atlas:anon:caspian", "anon-state");
    window.localStorage.setItem("atlas:caspian:foo", "legacy-caspian");
    window.localStorage.setItem("ehi-agent-settings", "legacy-agent");
    window.localStorage.setItem(
      "ehi-provider-assistant-context-packages",
      "legacy-context",
    );

    purgeWorkspaceState();

    expect(window.localStorage.getItem("atlas:demo:abc:caspian")).toBeNull();
    expect(window.localStorage.getItem("atlas:guest:gxyz:caspian")).toBeNull();
    expect(window.localStorage.getItem("atlas:caspian:foo")).toBeNull();
    expect(window.localStorage.getItem("ehi-agent-settings")).toBeNull();
    expect(
      window.localStorage.getItem("ehi-provider-assistant-context-packages"),
    ).toBeNull();
    expect(window.localStorage.getItem("atlas:auth:u1:caspian")).toBe("auth-state");
    expect(window.localStorage.getItem("atlas:anon:caspian")).toBe("anon-state");
  });

  it("migrateLegacyKey moves the legacy value into the new key and clears the legacy entry", () => {
    window.localStorage.setItem("legacy-key", "legacy-value");
    migrateLegacyKey("legacy-key", "new-key");
    expect(window.localStorage.getItem("new-key")).toBe("legacy-value");
    expect(window.localStorage.getItem("legacy-key")).toBeNull();
  });

  it("migrateLegacyKey does not overwrite an existing new key but clears the legacy entry", () => {
    window.localStorage.setItem("legacy-key", "legacy-value");
    window.localStorage.setItem("new-key", "already-set");
    migrateLegacyKey("legacy-key", "new-key");
    expect(window.localStorage.getItem("new-key")).toBe("already-set");
    expect(window.localStorage.getItem("legacy-key")).toBeNull();
  });
});
