import { describe, expect, test } from "bun:test";
import { greet, workspaceAnchor } from "../src/index";

describe("web service greeting", () => {
  test("greet includes the target name", () => {
    expect(greet("world")).toContain("hello, world");
  });

  test("greet mentions the web service", () => {
    expect(greet("world")).toContain("web service");
  });

  test("workspace anchor identifies bun", () => {
    expect(workspaceAnchor()).toBe("bun");
  });
});
