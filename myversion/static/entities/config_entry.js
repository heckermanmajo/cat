/**
 * @class ConfigEntry
 * @extends Entity
 * @property {number} id
 * @property {number} created_at
 * @property {number} updated_at
 * @property {string} key
 * @property {string} value
 * @property {string} description
 */
class ConfigEntry extends Entity {
    static _name = 'configentry';
    static _defaults = { key: '', value: '', description: '' };

    static async set(key, value) {
        const all = await this.all();
        let entry = all.find(e => e.key === key);
        if (entry) entry.value = value;
        else entry = new ConfigEntry({ key, value });
        return await entry.save();
    }

    /** @return Promise<?string> */
    static async get(key) {
        const all = await this.all();
        const entry = all.find(e => e.key === key);
        return entry ? entry.value : null;
    }
}
