# modules/settings_manager.py
from models.settings_model import Setting

class SettingsManager:
    """
    Manages application settings, providing a simple interface
    to get and set configuration values stored in the database.
    """
    def __init__(self):
        """Ensures the settings table exists when the manager is initialized."""
        Setting._create_table()

    def get_setting(self, key, default=None):
        """
        Retrieves a setting's value.

        Args:
            key (str): The name of the setting.
            default: The value to return if the setting is not found.

        Returns:
            The value of the setting, or the default value.
        """
        return Setting.get(key, default)

    def set_setting(self, key, value):
        """
        Saves a setting's value.

        Args:
            key (str): The name of the setting.
            value (str): The value to save.

        Returns:
            bool: True if successful, False otherwise.
        """
        return Setting.set(key, str(value)) # Ensure value is stored as text

