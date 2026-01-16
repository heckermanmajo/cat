import json
import time
from typing import Dict, List, Tuple


class MembersFilter:
    """
    Members filter needs to be able to be translated into sql.
    """
    sort_by: str = 'name_asc'
    search_term: str = ''
    community_slug: str = ''
    include_by: str = '{}'
    exclude_by: str = '{}'

    def __init__(self, data: dict = None):
        if data:
            self.sort_by = data.get('sortBy', 'name_asc')
            self.search_term = data.get('searchTerm', '')
            self.community_slug = data.get('communitySlug', '')
            self.include_by = json.dumps(data.get('include', {}))
            self.exclude_by = json.dumps(data.get('exclude', {}))

    def _build_conditions(self, filters: Dict, negate: bool = False) -> Tuple[List[str], List]:
        """Build SQL conditions from filter dict. If negate=True, conditions are inverted."""
        conditions = []
        args = []
        now = int(time.time())
        day_seconds = 86400

        for key, val in filters.items():
            if val is None or val == '' or val == -1 or val == '-1':
                continue

            if key == 'member_role':
                if negate:
                    conditions.append("member_role != ?")
                else:
                    conditions.append("member_role = ?")
                args.append(val)

            elif key == 'active_since':
                days = int(val)
                threshold = now - (days * day_seconds)
                if negate:
                    conditions.append("last_active < ?")
                else:
                    conditions.append("last_active >= ?")
                args.append(threshold)

            elif key == 'inactive_since':
                days = int(val)
                threshold = now - (days * day_seconds)
                if negate:
                    conditions.append("last_active >= ?")
                else:
                    conditions.append("last_active < ?")
                args.append(threshold)

            elif key == 'joined_since':
                days = int(val)
                threshold = now - (days * day_seconds)
                if negate:
                    conditions.append("member_created_at < ?")
                else:
                    conditions.append("member_created_at >= ?")
                args.append(threshold)

            elif key == 'joined_before':
                days = int(val)
                threshold = now - (days * day_seconds)
                if negate:
                    conditions.append("member_created_at >= ?")
                else:
                    conditions.append("member_created_at < ?")
                args.append(threshold)

            elif key == 'points_min':
                points = int(val)
                if negate:
                    conditions.append("points < ?")
                else:
                    conditions.append("points >= ?")
                args.append(points)

            elif key == 'points_max':
                points = int(val)
                if negate:
                    conditions.append("points > ?")
                else:
                    conditions.append("points <= ?")
                args.append(points)

            elif key == 'is_online':
                if val is True or val == 'true':
                    if negate:
                        conditions.append("is_online = 0")
                    else:
                        conditions.append("is_online = 1")

            elif key == 'is_former_member':
                if val is True or val == 'true':
                    # Former member = NOT in latest fetch batch (same day as most recent fetch)
                    # Uses community_slug from filter (passed as arg) for performance
                    subquery = """
                        skool_id NOT IN (
                            SELECT DISTINCT u2.skool_id FROM user u2
                            WHERE u2.fetch_id IN (
                                SELECT f.id FROM fetch f
                                WHERE f.type = 'members' AND f.community_slug = ?
                                AND date(f.created_at, 'unixepoch') = (
                                    SELECT date(f2.created_at, 'unixepoch') FROM fetch f2
                                    WHERE f2.type = 'members' AND f2.community_slug = ?
                                    ORDER BY f2.created_at DESC LIMIT 1
                                )
                            )
                        )
                    """
                    if negate:
                        conditions.append(subquery.replace("NOT IN", "IN"))
                    else:
                        conditions.append(subquery)
                    # Need community_slug twice for the subquery
                    args.append(self.community_slug)
                    args.append(self.community_slug)

        return conditions, args

    def _get_order_by(self) -> str:
        """Convert sortBy value to SQL ORDER BY clause."""
        sort_map = {
            'name_asc': 'name ASC',
            'name_desc': 'name DESC',
            'points_asc': 'points ASC',
            'points_desc': 'points DESC',
            'last_active_asc': 'last_active ASC',
            'last_active_desc': 'last_active DESC',
            'joined_asc': 'member_created_at ASC',
            'joined_desc': 'member_created_at DESC',
        }
        return sort_map.get(self.sort_by, 'name ASC')

    def to_sql(self) -> Tuple[str, List]:
        """Build complete SQL query with filters, search, and sorting."""
        sql = "SELECT * FROM user WHERE 1=1"
        args = []

        # Community filter (required - no community = no results)
        if self.community_slug:
            sql += " AND community_slug = ?"
            args.append(self.community_slug)
        else:
            sql += " AND 1=0"  # No community set -> return empty

        # Search term
        if self.search_term:
            sql += " AND (name LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)"
            search_pattern = f"%{self.search_term}%"
            args.extend([search_pattern, search_pattern, search_pattern, search_pattern])

        # Include conditions (AND)
        include_filters = json.loads(self.include_by) if self.include_by else {}
        include_conds, include_args = self._build_conditions(include_filters, negate=False)
        for cond in include_conds:
            sql += f" AND {cond}"
        args.extend(include_args)

        # Exclude conditions (AND NOT)
        exclude_filters = json.loads(self.exclude_by) if self.exclude_by else {}
        exclude_conds, exclude_args = self._build_conditions(exclude_filters, negate=True)
        for cond in exclude_conds:
            sql += f" AND {cond}"
        args.extend(exclude_args)

        # Sorting
        sql += f" ORDER BY {self._get_order_by()}"

        return sql, args