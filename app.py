import os
from datetime import datetime
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from PIL import Image

# ==============================================================================
# 1. CORE APPLICATION ROUTING & BOOT CONFIGURATIONS
# ==============================================================================
app = Flask(
    __name__, 
    template_folder=os.path.join('app', 'templates'),
    static_folder=os.path.join('app', 'static')
)
app.config['SECRET_KEY'] = 'corporate_cricket_auction_ultra_secret_key'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(INSTANCE_DIR, 'auction.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*", hosted_js_api=True)

# Custom template filter for formatting integers to Indian numbering system currency notation format
@app.template_filter('toLocaleString')
def to_locale_string_filter(value):
    try:
        s = str(int(value))
        if len(s) <= 3:
            return s
        last_three = s[-3:]
        remaining = s[:-3]
        remaining = remaining[::-1]
        parts = []
        for i in range(0, len(remaining), 2):
            parts.append(remaining[i:i+2])
        remaining_str = ",".join(parts)[::-1]
        return remaining_str + "," + last_three
    except Exception:
        return value

# ==============================================================================
# 2. FILE SYSTEM PHOTOGRAPHY ENGINE (OPTIMIZATION AND COMPRESSION)
# ==============================================================================
def save_player_image(file, upload_folder):
    if not file or file.filename == '':
        return 'default_avatar.png'

    extension = file.filename.split('.')[-1].lower()
    if extension not in ['jpg', 'jpeg', 'png', 'webp']:
        extension = 'jpg'
        
    filename = secure_filename(f"{uuid4().hex}.{extension}")
    filepath = os.path.join(upload_folder, filename)

    try:
        image = Image.open(file)
        image = image.convert('RGB')
        image.thumbnail((400, 500))
        image.save(filepath, optimize=True, quality=80)
        return filename
    except Exception:
        return 'default_avatar.png'

# ==============================================================================
# 3. COMPREHENSIVE SCHEMAS & DATABASE CONFIGURATIONS
# ==============================================================================
class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    photo = db.Column(db.String(200), default='default_avatar.png')
    base_price = db.Column(db.Integer, default=1000)
    sold_price = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default='READY')  # READY, LIVE, SOLD, UNSOLD
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_name = db.Column(db.String(100), nullable=False, unique=True)
    captain_name = db.Column(db.String(100), nullable=False)
    purse = db.Column(db.Integer, default=100000)
    players = db.relationship('Player', backref='team', lazy=True)

class AuctionState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    current_player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=True)
    current_bid = db.Column(db.Integer, default=1000)
    # STATES: INITIALIZED, ACTIVE, BREAK, SOLD_SPLASH, UNSOLD_SPLASH, COMPLETED
    status = db.Column(db.String(20), default='INITIALIZED')
    
    last_sold_name = db.Column(db.String(100), nullable=True)
    last_sold_team = db.Column(db.String(100), nullable=True)
    last_sold_amount = db.Column(db.Integer, nullable=True)

class SoldHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_name = db.Column(db.String(100), nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ==============================================================================
# 4. PACKET STREAM HARNESS TRANSMITTERS (COMPREHENSIVE MULTI-DATA OBJECTS)
# ==============================================================================
def compile_live_state_payload(state):
    # Generates detailed relational mapping lists so roster portfolios sync dynamically
    teams_data = []
    for t in Team.query.all():
        roster_list = [{"name": p.full_name, "role": p.role, "price": p.sold_price} for p in t.players]
        teams_data.append({
            "id": t.id,
            "team_name": t.team_name,
            "captain_name": t.captain_name,
            "purse": t.purse,
            "roster": roster_list
        })
    
    if not state:
        return {"status": "INITIALIZED", "teams": teams_data}
        
    active_player = db.session.get(Player, state.current_player_id) if state.current_player_id else None
    
    return {
        "status": state.status,
        "current_bid": state.current_bid,
        "last_sold_name": state.last_sold_name,
        "last_sold_team": state.last_sold_team,
        "last_sold_amount": state.last_sold_amount,
        "teams": teams_data,
        "player": {
            "id": active_player.id,
            "full_name": active_player.full_name,
            "department": active_player.department,
            "role": active_player.role,
            "photo": active_player.photo,
            "base_price": active_player.base_price
        } if active_player else None
    }

def broadcast_live_system_update():
    state = AuctionState.query.first()
    payload = compile_live_state_payload(state)
    socketio.emit('global_auction_packet', payload)

# ==============================================================================
# 5. CORE REGULAR RENDERING ROUTINGS
# ==============================================================================
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/live')
def live_projector_screen():
    state = AuctionState.query.first()
    return render_template('live.html', initial_state=compile_live_state_payload(state))

@app.route('/players')
def player_list():
    return render_template('players.html', players=Player.query.all())

@app.route('/register', methods=['GET', 'POST'])
def register_player():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        department = request.form.get('department')
        role = request.form.get('role')
        photo_file = request.files.get('photo')

        filename = save_player_image(photo_file, app.config['UPLOAD_FOLDER'])

        new_player = Player(
            full_name=full_name,
            department=department,
            role=role,
            photo=filename
        )
        db.session.add(new_player)
        db.session.commit()
        return redirect('/players')

    return render_template('register.html')

@app.route('/teams', methods=['GET', 'POST'])
def handle_teams():
    if request.method == 'POST':
        t_name = request.form.get('team_name')
        c_name = request.form.get('captain_name')
        if t_name and c_name:
            db.session.add(Team(team_name=t_name, captain_name=c_name))
            db.session.commit()
        return redirect('/teams')
    return render_template('teams.html', teams=Team.query.all())

@app.route('/auctioneer')
def auctioneer_dashboard():
    state = AuctionState.query.first()
    
    # Safety Check: If the state somehow got deleted or didn't initialize, recreate it cleanly
    if not state:
        state = AuctionState(status='INITIALIZED', current_bid=1000)
        db.session.add(state)
        db.session.commit()
    
    teams = Team.query.all()
    total_ready = Player.query.filter_by(status='READY').count()
    
    # Broadcast an update down to synchronize all open windows instantly
    try:
        broadcast_live_system_update()
    except Exception as e:
        print(f"📡 [Socket Update] Waiting for active interface client handshakes: {e}")
        
    return render_template(
        'auctioneer.html',
        state=state,
        teams=teams,
        total_ready=total_ready
    )

# ==============================================================================
# 6. ADMINISTRATIVE ASYNCHRONOUS API CHANNELS (PREVENTS SCREEN TAKEOVERS)
# ==============================================================================
@app.route('/admin/player/edit/<int:player_id>', methods=['POST'])
def edit_player(player_id):
    player = db.session.get(Player, player_id) or abort(404)
    
    player.full_name = request.form.get('full_name', player.full_name)
    player.department = request.form.get('department', player.department)
    player.role = request.form.get('role', player.role)
    
    b_price = request.form.get('base_price')
    if b_price: 
        player.base_price = int(b_price)
        
    photo_file = request.files.get('photo')
    if photo_file and photo_file.filename != '':
        new_filename = save_player_image(photo_file, app.config['UPLOAD_FOLDER'])
        if player.photo and player.photo != 'default_avatar.png':
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], player.photo)
            if os.path.exists(old_path):
                try: os.remove(old_path)
                except Exception: pass
        player.photo = new_filename

    db.session.commit()
    broadcast_live_system_update()
    return jsonify({"status": "success", "message": "Player database row updated successfully"}), 200

@app.route('/admin/player/delete/<int:player_id>', methods=['POST'])
def delete_player(player_id):
    player = db.session.get(Player, player_id) or abort(404)
    
    # Restores wallet balances if an allocated roster space is deleted mid-flight
    if player.team_id and player.sold_price:
        team = db.session.get(Team, player.team_id)
        if team:
            team.purse += player.sold_price
            history_entry = SoldHistory.query.filter_by(player_name=player.full_name, team_name=team.team_name).first()
            if history_entry:
                db.session.delete(history_entry)

    state = AuctionState.query.first()
    if state and state.current_player_id == player.id:
        state.current_player_id = None
        state.current_bid = 0
        state.status = 'INITIALIZED'
        state.last_sold_name = None
        state.last_sold_team = None
        state.last_sold_amount = None

    if player.photo and player.photo != 'default_avatar.png':
        old_path = os.path.join(app.config['UPLOAD_FOLDER'], player.photo)
        if os.path.exists(old_path):
            try: os.remove(old_path)
            except Exception: pass

    db.session.delete(player)
    db.session.commit()
    broadcast_live_system_update()
    return jsonify({"status": "success", "message": "Player removed from roster data sets"}), 200


# ==============================================================================
# SPECIAL CONTROL DECK DIRECT HTTP OVERRIDES (BULLETPROOF CONTROL CHANNELS)
# ==============================================================================
@app.route('/admin/api/trigger/<string:event_name>', methods=['POST'])
def administrative_hardware_trigger(event_name):
    state = AuctionState.query.first()
    if not state:
        return jsonify({"status": "error", "message": "State missing"}), 400

    print(f"🎮 [API Override Triggered] Processing administrative event: {event_name}")

    if event_name == 'start_auction':
        if state.status == 'INITIALIZED':
            state.status = 'ACTIVE'
            first_up = Player.query.filter_by(status='READY').order_by(Player.id.asc()).first()
            if first_up:
                state.current_player_id = first_up.id
                state.current_bid = first_up.base_price
                first_up.status = 'LIVE'
            db.session.commit()

    elif event_name == 'increment_bid':
        if state.status == 'ACTIVE':
            state.current_bid += 1000
            db.session.commit()

    elif event_name == 'decrement_bid':
        if state.status == 'ACTIVE':
            p = db.session.get(Player, state.current_player_id)
            min_p = p.base_price if p else 1000
            if state.current_bid - 1000 >= min_p:
                state.current_bid -= 1000
                db.session.commit()

    elif event_name == 'mark_unsold':
        if state.status == 'ACTIVE':
            curr = db.session.get(Player, state.current_player_id)
            if curr:
                curr.status = 'UNSOLD'
                state.last_sold_name = curr.full_name
            state.status = 'UNSOLD_SPLASH'
            state.current_player_id = None
            db.session.commit()

    elif event_name == 'summon_next_player':
        if state.status in ['SOLD_SPLASH', 'UNSOLD_SPLASH', 'ACTIVE']:
            nxt = Player.query.filter_by(status='READY').order_by(Player.id.asc()).first()
            if nxt:
                state.status = 'ACTIVE'
                state.current_player_id = nxt.id
                state.current_bid = nxt.base_price
                nxt.status = 'LIVE'
            db.session.commit()

    elif event_name == 'recycle_unsold_pool':
        print("🔄 [Engine Action] Hard-resetting auction deck. Restoring budgets and pools.")
        
        # 1. Bring ALL players back to the READY pool, clear sold items
        for p in Player.query.all():
            p.status = 'READY'
            p.sold_price = None
            p.team_id = None
            
        # 2. Restore every single franchise wallet to its 100,000 value
        DEFAULT_PURSE = 100000 
        for team in Team.query.all():
            team.purse = DEFAULT_PURSE
            
        # 3. Wipe old trade history ledgers cleanly
        db.session.query(SoldHistory).delete()

        # 4. Re-initialize global system state variables
        state.status = 'INITIALIZED'
        state.current_player_id = None
        state.current_bid = 0
        state.last_sold_name = None
        state.last_sold_team = None
        state.last_sold_amount = None
        
        db.session.commit()

    elif event_name == 'toggle_halt_break':
        if state.status == 'BREAK':
            state.status = 'ACTIVE'
        elif state.status == 'ACTIVE':
            state.status = 'BREAK'
        db.session.commit()

    elif event_name == 'finalize_close_auction':
        state.status = 'COMPLETED'
        state.current_player_id = None
        db.session.commit()

    # BROADCAST NEW DATA INSTANTLY TO ALL VISUAL SCREENS
    broadcast_live_system_update()
    return jsonify({"status": "success", "current_status": state.status}), 200

# Update the franchise assignment call to also support direct APIs
@app.route('/admin/api/sell_player/<int:team_id>', methods=['POST'])
def administrative_sell_trigger(team_id):
    state = AuctionState.query.first()
    curr = db.session.get(Player, state.current_player_id) if state else None
    team = db.session.get(Team, team_id) if curr else None

    if curr and team:
        if team.purse < state.current_bid:
            return jsonify({"status": "error", "message": "Exceeded! Team budget purse depleted."}), 400

        curr.status = 'SOLD'
        curr.sold_price = state.current_bid
        curr.team_id = team.id
        team.purse -= state.current_bid

        db.session.add(SoldHistory(player_name=curr.full_name, team_name=team.team_name, amount=state.current_bid))
        
        state.status = 'SOLD_SPLASH'
        state.last_sold_name = curr.full_name
        state.last_sold_team = team.team_name
        state.last_sold_amount = state.current_bid
        state.current_player_id = None
        
        db.session.commit()
        broadcast_live_system_update()
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error", "message": "No active player or franchise matching criteria"}), 400

# ==============================================================================
# 7. REAL-TIME ENGINE WEBSOCKET HANDLERS
# ==============================================================================
@socketio.on('start_auction')
def handle_start_auction():
    state = AuctionState.query.first()
    if state and state.status == 'INITIALIZED':
        state.status = 'ACTIVE'
        first_up = Player.query.filter_by(status='READY').order_by(Player.id.asc()).first()
        if first_up:
            state.current_player_id = first_up.id
            state.current_bid = first_up.base_price
            first_up.status = 'LIVE'
        db.session.commit()
        broadcast_live_system_update()

@socketio.on('connect')
def handle_client_connect():
    """ Runs immediately when any dashboard or display tab opens/refreshes """
    # 1. Fetch the active state object directly from the database
    state = AuctionState.query.first()
    
    # 2. Pass the state object into the payload function as required
    initial_packet = compile_live_state_payload(state)
    
    # 3. Emit PRIVATELY only to the single socket client that just connected
    emit('global_auction_packet', initial_packet)

@socketio.on('increment_bid')
def handle_increment_bid():
    state = AuctionState.query.first()
    if state and state.status == 'ACTIVE':
        state.current_bid += 1000
        db.session.commit()
        broadcast_live_system_update()

@socketio.on('decrement_bid')
def handle_decrement_bid():
    state = AuctionState.query.first()
    if state and state.status == 'ACTIVE':
        p = db.session.get(Player, state.current_player_id)
        min_p = p.base_price if p else 1000
        if state.current_bid - 1000 >= min_p:
            state.current_bid -= 1000
            db.session.commit()
            broadcast_live_system_update()

@socketio.on('mark_unsold')
def handle_mark_unsold():
    state = AuctionState.query.first()
    if state and state.status == 'ACTIVE':
        curr = db.session.get(Player, state.current_player_id)
        if curr:
            curr.status = 'UNSOLD'
            state.last_sold_name = curr.full_name
            
        state.status = 'UNSOLD_SPLASH'
        state.current_player_id = None
        db.session.commit()
        broadcast_live_system_update()

@socketio.on('sold_player')
def handle_sold_player(data):
    state = AuctionState.query.first()
    curr = db.session.get(Player, state.current_player_id) if state else None
    team = db.session.get(Team, data.get('team_id')) if curr else None

    if curr and team:
        if team.purse < state.current_bid:
            socketio.emit('error_alert', {'message': 'Exceeded! Team budget purse depleted.'})
            return

        curr.status = 'SOLD'
        curr.sold_price = state.current_bid
        curr.team_id = team.id
        team.purse -= state.current_bid

        db.session.add(SoldHistory(player_name=curr.full_name, team_name=team.team_name, amount=state.current_bid))
        
        state.status = 'SOLD_SPLASH'
        state.last_sold_name = curr.full_name
        state.last_sold_team = team.team_name
        state.last_sold_amount = state.current_bid
        state.current_player_id = None
        
        db.session.commit()
        broadcast_live_system_update()

@socketio.on('summon_next_player')
def handle_summon_next():
    state = AuctionState.query.first()
    if state and state.status in ['SOLD_SPLASH', 'UNSOLD_SPLASH', 'ACTIVE']:
        nxt = Player.query.filter_by(status='READY').order_by(Player.id.asc()).first()
        if nxt:
            state.status = 'ACTIVE'
            state.current_player_id = nxt.id
            state.current_bid = nxt.base_price
            nxt.status = 'LIVE'
        else:
            socketio.emit('error_alert', {'message': 'Roster pool empty. Mark Auction Completed when ready.'})
        db.session.commit()
        broadcast_live_system_update()

@socketio.on('recycle_unsold_pool')
def handle_recycle_unsold_pool():
    for p in Player.query.filter_by(status='UNSOLD').all():
        p.status = 'READY'
    db.session.commit()
    
    state = AuctionState.query.first()
    if state:
        state.status = 'INITIALIZED'
        state.current_player_id = None
        state.current_bid = 0
        state.last_sold_name = None
        state.last_sold_team = None
        state.last_sold_amount = None
    db.session.commit()
    broadcast_live_system_update()

@socketio.on('toggle_halt_break')
def handle_halt_toggle():
    state = AuctionState.query.first()
    if state:
        if state.status == 'BREAK':
            state.status = 'ACTIVE'
        elif state.status == 'ACTIVE':
            state.status = 'BREAK'
        db.session.commit()
        broadcast_live_system_update()

@socketio.on('finalize_close_auction')
def handle_finalize_close():
    state = AuctionState.query.first()
    if state:
        state.status = 'COMPLETED'
        state.current_player_id = None
        db.session.commit()
        broadcast_live_system_update()

# ==============================================================================
# 8. APPLICATION DATA CLEANUP SEED LOOPS
# ==============================================================================
with app.app_context():
    db.create_all()
    stale_csv_players = Player.query.filter_by(status='Available').all()
    if stale_csv_players:
        for p in stale_csv_players:
            p.status = 'READY'
        db.session.commit()

    if not AuctionState.query.first():
        db.session.add(AuctionState())
        db.session.commit()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)