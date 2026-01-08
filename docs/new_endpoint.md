  1. Backend (Python) - in der Model-Klasse:

  # src/config_entry.py
  class ConfigEntry(Model):
      key: str = ""
      value: str = ""
      description: str = ""

      @classmethod
      def register(cls, app):
          super().register(app)  # Standard CRUD

          @app.route('/api/configentry/by-key/<key>', methods=['GET'])
          def get_by_key(key):
              items = cls.get_list(f"SELECT * FROM configentry WHERE key = ?", [key])
              return jsonify([x.to_dict() for x in items])

  2. Frontend (JS) - in der Entity-Klasse:

  // GGF. -> JS DOC updaten

  // entities/config_entry.js
  class ConfigEntry extends Entity {
      static _name = 'configentry';
      static _defaults = { key: '', value: '', description: '' };

      static async byKey(key) {
          const res = await get(`/api/configentry/by-key/${key}`);
          return res.ok ? res.data.map(d => new this(d)) : [];
      }
  }

  3. Verwenden:

  const entries = await ConfigEntry.byKey('theme');
