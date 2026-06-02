pub const SERVICE_NAME: &str = "edge";
pub const WORKSPACE_TOOL: &str = "cargo";

#[must_use]
pub fn greet(name: &str) -> String {
    format!("hello, {name}, from the {SERVICE_NAME} service")
}

#[must_use]
pub fn workspace_anchor() -> &'static str {
    WORKSPACE_TOOL
}

#[cfg(test)]
mod tests {
    use super::{greet, workspace_anchor};

    #[test]
    fn greet_includes_target_name() {
        assert!(greet("world").contains("hello, world"));
    }

    #[test]
    fn greet_mentions_edge_service() {
        assert!(greet("world").contains("edge service"));
    }

    #[test]
    fn workspace_anchor_identifies_cargo() {
        assert_eq!(workspace_anchor(), "cargo");
    }
}
