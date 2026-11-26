from django.apps import AppConfig


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agent"
    verbose_name = "AI Emergency Agent"

    def ready(self):
        # Auto-import tools to ensure all tools are registered with the central registry
        import apps.agent.tools  # noqa: F401
