export const SERVICE_NAME = "web";
export const WORKSPACE_TOOL = "bun";

export function greet(name: string): string {
  return `hello, ${name}, from the ${SERVICE_NAME} service`;
}

export function workspaceAnchor(): string {
  return WORKSPACE_TOOL;
}
