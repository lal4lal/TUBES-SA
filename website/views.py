from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from .models import User, Booking, Driver, db
import csv
import csv
from flask import request
from werkzeug.utils import secure_filename
from datetime import datetime
import os

views = Blueprint('views', __name__)

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_csv(file_path):
    bookings = []
    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                bookings.append({
                    'booking_id': row['Booking ID'],
                    'pickup_time': datetime.fromisoformat(row['Pickup Time']),
                    'drop_off_time': datetime.fromisoformat(row['Drop-off Time'])
                })
            except ValueError as e:
                flash(f"Error parsing CSV: {e}", category='error')
                return []
    return bookings


def create_adjacency_matrix(bookings):
    n = len(bookings)
    graph = [[0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if not (bookings[i]['drop_off_time'] <= bookings[j]['pickup_time'] or bookings[j]['drop_off_time'] <= bookings[i]['pickup_time']):
                graph[i][j] = graph[j][i] = 1
    return graph

def is_safe(v, graph, color, c):
    for i in range(len(graph)):
        if graph[v][i] and c == color[i]:
            return False
    return True

def graph_coloring_util(graph, m, color, v):
    if v == len(graph):
        return True

    for c in range(1, m + 1):
        if is_safe(v, graph, color, c):
            color[v] = c
            if graph_coloring_util(graph, m, color, v + 1):
                return True
            color[v] = 0
    return False

def graph_coloring(graph, m):
    color = [0] * len(graph)
    if not graph_coloring_util(graph, m, color, 0):
        return False, []
    return True, color

def backtracking_scheduler(bookings):
    n = len(bookings)
    graph = create_adjacency_matrix(bookings)
    drivers = Driver.query.all()

    success, color = graph_coloring(graph, len(drivers))
    if not success:
        flash("No solution exists", category='error')
        return []

    for i in range(n):
        bookings[i]['driver_id'] = drivers[color[i] - 1].id

    return bookings


# Greedy algorithm for graph coloring
def greedy_scheduler(bookings):
    n = len(bookings)
    graph = create_adjacency_matrix(bookings)
    result = [-1] * n
    result[0] = 0
    drivers = Driver.query.all()
    available = [False] * n

    for u in range(1, n):
        for i in range(n):
            if graph[u][i] and result[i] != -1:
                available[result[i]] = True

        cr = 0
        while cr < n:
            if not available[cr]:
                break
            cr += 1

        result[u] = cr
        available = [False] * n

    for i in range(n):
        bookings[i]['driver_id'] = drivers[result[i]].id

    return bookings

UPLOAD_FOLDER = '/Users/HilalAbyan/Docs/Telkom University/Semester 4/Strategi Algoritma/TUBES SA/website/uploads' 
# views.py

# Initialize the uploaded_filename as a list globally
uploaded_filename = []

@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    global uploaded_filename  # Ensure that you are modifying the global list
    if request.method == 'POST':
        file = request.files['csv_file']
        algorithm = request.form.get('algorithm')
        if not file:
            flash('No file uploaded', category='error')
            return render_template('home.html', user=current_user)

        if file:
            if uploaded_filename is None:
                uploaded_filename = []
            filename = secure_filename(file.filename)
            uploaded_filename.append(filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)  # Save the file to the upload folder

            bookings = []
            try:
                with open(file_path, 'r') as csvfile:
                    csv_input = csv.reader(csvfile)
                    next(csv_input)  # Skip header row
                    for row in csv_input:
                        if len(row) != 3:
                            flash('Invalid CSV format: Each row should contain Booking ID, Pickup Time, and Drop-off Time.', category='error')
                            return render_template('home.html', user=current_user)
                        booking_id, pickup_time, drop_off_time = row
                        bookings.append({
                            'booking_id': booking_id,
                            'pickup_time': datetime.fromisoformat(pickup_time),
                            'drop_off_time': datetime.fromisoformat(drop_off_time),
                        })
            except ValueError as e:
                flash(f"Error parsing CSV: {e}", category='error')
                return render_template('home.html', user=current_user)

            if algorithm == 'backtracking':
                scheduled_bookings = backtracking_scheduler(bookings)
            elif algorithm == 'greedy':
                scheduled_bookings = greedy_scheduler(bookings)
            else:
                flash('Invalid scheduling algorithm selected', category='error')
                return render_template('home.html', user=current_user)

            # Save bookings to database
            for booking in scheduled_bookings:
                new_booking = Booking(
                    booking_id=booking['booking_id'],
                    pickup_time=booking['pickup_time'],
                    drop_off_time=booking['drop_off_time'],
                    driver_id=booking['driver_id']
                )
                db.session.add(new_booking)
            db.session.commit()

            flash('Drivers scheduled successfully!', category='success')
            return render_template('home.html', user=current_user, bookings=scheduled_bookings, Driver=Driver)
    return render_template('home.html', user=current_user)

@views.route('/delete-bookings', methods=['POST'])
def delete_bookings():
    global uploaded_filename
    confirm = request.form.get('confirm')
    if confirm == 'true':
        # Delete all bookings
        Booking.query.delete()
        db.session.commit()
        flash('All bookings deleted successfully!', category='success')
        if uploaded_filename:
            uploaded_file_path = os.path.join(UPLOAD_FOLDER, uploaded_filename[0])  # Adjust the file name accordingly
            if os.path.exists(uploaded_file_path):
                os.remove(uploaded_file_path)
                flash('Uploaded file deleted successfully!', category='success')
            else:
                flash('Uploaded file not found!', category='error')
            uploaded_filename = []
        else:
            flash('No file uploaded to delete!', category='error')
    else:
        flash('Confirmation required to delete bookings!', category='error')
    return redirect(url_for('views.home'))
