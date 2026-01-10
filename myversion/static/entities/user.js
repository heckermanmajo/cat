/**
 * @class User
 * @extends Entity
 * @property {number} id
 * @property {number} created_at
 * @property {number} updated_at
 * @property {number} fetch_id
 * @property {number} fetched_at
 * @property {string} community_slug
 * @property {string} skool_id
 * @property {string} name
 * @property {string} email
 * @property {string} first_name
 * @property {string} last_name
 * @property {string} skool_created_at
 * @property {string} skool_updated_at
 * @property {string} metadata
 * @property {string} member_id
 * @property {string} member_role
 * @property {string} member_group_id
 * @property {string} member_created_at
 * @property {string} member_metadata
 */
class User extends Entity {
    static _name = 'user';
    static _defaults = {
        fetch_id: 0,
        fetched_at: 0,
        community_slug: '',
        skool_id: '',
        name: '',
        email: '',
        first_name: '',
        last_name: '',
        skool_created_at: '',
        skool_updated_at: '',
        metadata: '',
        member_id: '',
        member_role: '',
        member_group_id: '',
        member_created_at: '',
        member_metadata: ''
    };
}
