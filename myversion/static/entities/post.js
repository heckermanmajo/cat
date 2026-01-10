/**
 * @class Post
 * @extends Entity
 * @property {number} id
 * @property {number} created_at
 * @property {number} updated_at
 * @property {number} fetch_id
 * @property {number} fetched_at
 * @property {string} community_slug
 * @property {string} skool_id
 * @property {string} name
 * @property {string} post_type
 * @property {string} group_id
 * @property {string} user_id
 * @property {string} label_id
 * @property {string} root_id
 * @property {string} skool_created_at
 * @property {string} skool_updated_at
 * @property {string} metadata
 * @property {number} is_toplevel
 * @property {number} comments
 * @property {number} upvotes
 * @property {string} user_name
 * @property {string} user_metadata
 */
class Post extends Entity {
    static _name = 'post';
    static _defaults = {
        fetch_id: 0,
        fetched_at: 0,
        community_slug: '',
        skool_id: '',
        name: '',
        post_type: '',
        group_id: '',
        user_id: '',
        label_id: '',
        root_id: '',
        skool_created_at: '',
        skool_updated_at: '',
        metadata: '',
        is_toplevel: 0,
        comments: 0,
        upvotes: 0,
        user_name: '',
        user_metadata: ''
    };
}
