// API Functions
async function api(method, url, body = null) {
    const opts = { method, headers: {} };
    if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    console.log(`[API] ${method} ${url}`, body || '');

    try {
        const res = await fetch(url, opts);
        const text = await res.text();
        if (!res.ok) { console.error(`[API] ${res.status}:`, text); return { ok: false, status: res.status, error: text }; }
        try {
            const data = text ? JSON.parse(text) : null;
            console.log(`[API] Response:`, data);
            return { ok: true, status: res.status, data };
        } catch {
            console.log(`[API] HTML:`, text.slice(0, 100));
            return { ok: true, status: res.status, html: text };
        }
    } catch (e) {
        console.error(`[API] Network error:`, e.message);
        return { ok: false, status: 0, error: e.message };
    }
}

function get(url) { return api('GET', url); }
function post(url, data) { return api('POST', url, data); }
function put(url, data) { return api('PUT', url, data); }
function del(url) { return api('DELETE', url); }

// Entity Base
class Entity {
    static _name = 'entity';
    static _defaults = {};

    constructor(data = {}) {
        this.id = null;
        this.created_at = 0;
        this.updated_at = 0;
        Object.assign(this, this.constructor._defaults, data);
    }

    get _endpoint() { return `/api/${this.constructor._name}`; }
    get _fields() { return Object.keys(this.constructor._defaults); }

    toJSON() {
        const obj = {};
        for (const k of this._fields) obj[k] = this[k];
        return obj;
    }

    async save() {
        const url = this.id ? `${this._endpoint}/${this.id}` : this._endpoint;
        const res = await api(this.id ? 'PUT' : 'POST', url, this.toJSON());
        if (res.ok) Object.assign(this, res.data);
        return res;
    }

    async delete() {
        if (!this.id) return { ok: false, error: 'No ID' };
        return await del(`${this._endpoint}/${this.id}`);
    }

    async render(mode = 'card') {
        if (!this.id) return { ok: false, error: 'No ID' };
        return await get(`${this._endpoint}/${this.id}/render/${mode}`);
    }

    static async all() {
        const res = await get(`/api/${this._name}`);
        return res.ok ? res.data.map(d => new this(d)) : [];
    }

    static async get(id) {
        const res = await get(`/api/${this._name}/${id}`);
        return res.ok ? new this(res.data) : null;
    }

    static async renderAll(mode = 'card') {
        return await get(`/api/${this._name}/render/${mode}`);
    }
}
