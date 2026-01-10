import json
from typing import Dict


class MembersFilter:
    """
    Members filter needs to be able to be translated into sql.
    """
    sort_by: str = 'id'
    sort_order: str = 'DESC'
    search_term: str = ''
    community_slug: str = ''

    exclude_by: str = '' # json
    include_by: str = '' # json

    def to_sql(self) -> tuple[str, list]:

        sql = "SELECT * FROM user WHERE 1=1"
        args = []

        if self.community_slug:
            args = self.community_slug
            sql += " AND community_slug = ?"

        if self.search_term: pass

        includeJson: Dict = json.loads(self.include_by)
        excludeJson: Dict = json.loads(self.exclude_by)

        if 'modadmin' in includeJson.keys(): pass
        if 'modadmin' in excludeJson.keys(): pass

        return sql, args