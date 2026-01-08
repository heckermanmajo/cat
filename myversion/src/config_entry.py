from model import Model

class ConfigEntry(Model):
    key: str = ""
    value: str = ""
    description: str = ""

    @classmethod
    def getByKey(cls, key):
        asList = cls.get_list(f"SELECT * FROM {cls.get_tablename()} WHERE `key` = ?", [key])
        return asList[0] if asList else None
