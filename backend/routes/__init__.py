"""Route registration and blueprint management"""

def register_routes(app):
    """Register all application blueprints"""
    from .position_tuner import position_bp
    from .debug import debug_bp
    from .admin import admin_bp
    from .user import user_bp
    from .misc import misc_bp
    from .payment import payment_bp
    
    # Register blueprints
    app.register_blueprint(position_bp, url_prefix='/api/positions')
    app.register_blueprint(debug_bp, url_prefix='/debug')
    app.register_blueprint(admin_bp, url_prefix='/admin') 
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(misc_bp)  # No prefix for misc routes
    app.register_blueprint(payment_bp, url_prefix='/payment')
