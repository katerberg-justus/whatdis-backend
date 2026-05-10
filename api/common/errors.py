from flask import jsonify


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error=str(e)), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify(error="Unauthorized"), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify(error="Forbidden"), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Not found"), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify(error="Too many requests"), 429

    @app.errorhandler(500)
    def internal(e):
        return jsonify(error="Internal server error"), 500
