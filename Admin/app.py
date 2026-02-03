from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

# -------------------------
# In-memory demo data (fast + submission-safe)
# -------------------------

users_data = [
    {"id": 1, "name": "Angela Wong Xin Yi", "role": "System Admin", "status": "Active"},
    {"id": 2, "name": "Thulasie Ganesan", "role": "Operations Admin", "status": "Active"},
    {"id": 3, "name": "Nur Afia", "role": "Analytics Admin", "status": "Suspended"},
    {"id": 4, "name": "Damia Irdina", "role": "Event Moderator", "status": "Active"},
]

inventory_data = [
    {"id": 1, "blood_type": "O+", "quantity_ml": 1200},
    {"id": 2, "blood_type": "A-", "quantity_ml": 450},
    {"id": 3, "blood_type": "B+", "quantity_ml": 900},
    {"id": 4, "blood_type": "AB+", "quantity_ml": 200},
]

blood_requests_data = [
    {"id": 1, "requester": "General Hospital", "blood_type": "O+", "quantity_ml": 300, "status": "Pending", "created_at": "2026-02-01 10:10"},
    {"id": 2, "requester": "City Clinic", "blood_type": "A-", "quantity_ml": 200, "status": "Approved", "created_at": "2026-02-01 11:15"},
]

inventory_logs = [
    {"id": 1, "inventory_id": 1, "action": "UPDATE", "old_quantity": 1000, "new_quantity": 1200, "changed_by": "Admin", "changed_at": "2026-02-01 09:55"},
]

request_logs = [
    {"id": 1, "request_id": 1, "action": "CREATE", "old_status": "-", "new_status": "Pending", "changed_by": "Admin", "changed_at": "2026-02-01 10:10"},
    {"id": 2, "request_id": 2, "action": "CREATE", "old_status": "-", "new_status": "Approved", "changed_by": "Admin", "changed_at": "2026-02-01 11:15"},
]


# -------------------------
# Helpers
# -------------------------

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def next_id(items):
    if not items:
        return 1
    return max(x["id"] for x in items) + 1


def summary_counts():
    total_users = len(users_data)
    active_users = sum(1 for u in users_data if u["status"] == "Active")
    suspended_users = total_users - active_users

    total_inventory_types = len(inventory_data)
    total_inventory_ml = sum(i["quantity_ml"] for i in inventory_data)
    low_stock = [i for i in inventory_data if i["quantity_ml"] < 500]

    total_requests = len(blood_requests_data)
    pending_requests = sum(1 for r in blood_requests_data if r["status"] == "Pending")
    approved_requests = sum(1 for r in blood_requests_data if r["status"] == "Approved")
    fulfilled_requests = sum(1 for r in blood_requests_data if r["status"] == "Fulfilled")

    return {
        "total_users": total_users,
        "active_users": active_users,
        "suspended_users": suspended_users,
        "total_inventory_types": total_inventory_types,
        "total_inventory_ml": total_inventory_ml,
        "low_stock": low_stock,
        "total_requests": total_requests,
        "pending_requests": pending_requests,
        "approved_requests": approved_requests,
        "fulfilled_requests": fulfilled_requests,
    }


def add_inventory_log(inventory_id, action, old_q, new_q, changed_by="Admin"):
    inventory_logs.insert(0, {
        "id": next_id(inventory_logs),
        "inventory_id": inventory_id,
        "action": action,
        "old_quantity": old_q,
        "new_quantity": new_q,
        "changed_by": changed_by,
        "changed_at": now_str()
    })


def add_request_log(request_id, action, old_status, new_status, changed_by="Admin"):
    request_logs.insert(0, {
        "id": next_id(request_logs),
        "request_id": request_id,
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "changed_by": changed_by,
        "changed_at": now_str()
    })


# -------------------------
# Routes
# -------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    counts = summary_counts()
    latest_inventory = inventory_logs[:5]
    latest_requests = request_logs[:5]
    return render_template(
        "dashboard.html",
        counts=counts,
        latest_inventory=latest_inventory,
        latest_requests=latest_requests
    )


# ---- Manage Users ----

@app.route("/manage_users", methods=["GET", "POST"])
def manage_users():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "").strip()
        status = request.form.get("status", "Active").strip()

        if name and role:
            users_data.append({
                "id": next_id(users_data),
                "name": name,
                "role": role,
                "status": status if status in ("Active", "Suspended") else "Active"
            })
        return redirect(url_for("manage_users"))

    return render_template("manage_users.html", users=users_data)


@app.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    user = next((u for u in users_data if u["id"] == user_id), None)
    if not user:
        return redirect(url_for("manage_users"))

    if request.method == "POST":
        user["name"] = request.form.get("name", user["name"]).strip()
        user["role"] = request.form.get("role", user["role"]).strip()
        status = request.form.get("status", user["status"]).strip()
        user["status"] = status if status in ("Active", "Suspended") else user["status"]
        return redirect(url_for("manage_users"))

    return render_template("edit_user.html", user=user)


@app.route("/users/toggle/<int:user_id>")
def toggle_user(user_id):
    user = next((u for u in users_data if u["id"] == user_id), None)
    if user:
        user["status"] = "Suspended" if user["status"] == "Active" else "Active"
    return redirect(url_for("manage_users"))


@app.route("/users/delete/<int:user_id>")
def delete_user(user_id):
    global users_data
    users_data = [u for u in users_data if u["id"] != user_id]
    return redirect(url_for("manage_users"))


# ---- Blood Management (Inventory) ----

@app.route("/blood_management", methods=["GET", "POST"])
def blood_management():
    if request.method == "POST":
        action = request.form.get("action")
        item_id = int(request.form.get("id"))
        qty = int(request.form.get("quantity_ml"))

        item = next((i for i in inventory_data if i["id"] == item_id), None)
        if item:
            old_q = item["quantity_ml"]

            if action == "set":
                new_q = max(0, qty)
                item["quantity_ml"] = new_q
                add_inventory_log(item_id, "UPDATE", old_q, new_q)

            elif action == "add":
                new_q = old_q + max(0, qty)
                item["quantity_ml"] = new_q
                add_inventory_log(item_id, "ADD", old_q, new_q)

            elif action == "remove":
                new_q = max(0, old_q - max(0, qty))
                item["quantity_ml"] = new_q
                add_inventory_log(item_id, "REMOVE", old_q, new_q)

        return redirect(url_for("blood_management"))

    low_stock = [i for i in inventory_data if i["quantity_ml"] < 500]
    return render_template("blood_management.html", inventory=inventory_data, low_stock=low_stock)


# ---- Blood Requests ----

@app.route("/blood_requests", methods=["GET", "POST"])
def blood_requests():
    if request.method == "POST":
        requester = request.form.get("requester", "").strip()
        blood_type = request.form.get("blood_type", "").strip()
        quantity_ml = int(request.form.get("quantity_ml", "0"))

        if requester and blood_type and quantity_ml > 0:
            new_id = next_id(blood_requests_data)
            created = now_str()
            blood_requests_data.append({
                "id": new_id,
                "requester": requester,
                "blood_type": blood_type,
                "quantity_ml": quantity_ml,
                "status": "Pending",
                "created_at": created
            })
            add_request_log(new_id, "CREATE", "-", "Pending")

        return redirect(url_for("blood_requests"))

    return render_template("blood_requests.html", requests=blood_requests_data)


@app.route("/requests/status/<int:req_id>/<new_status>")
def update_request_status(req_id, new_status):
    if new_status not in ("Pending", "Approved", "Fulfilled"):
        return redirect(url_for("blood_requests"))

    req = next((r for r in blood_requests_data if r["id"] == req_id), None)
    if req:
        old = req["status"]
        req["status"] = new_status
        add_request_log(req_id, "STATUS", old, new_status)

    return redirect(url_for("blood_requests"))


@app.route("/requests/delete/<int:req_id>")
def delete_request(req_id):
    global blood_requests_data
    blood_requests_data = [r for r in blood_requests_data if r["id"] != req_id]
    add_request_log(req_id, "DELETE", "-", "-")
    return redirect(url_for("blood_requests"))


# ---- Analytics ----

@app.route("/analytics")
def analytics():
    counts = summary_counts()
    inv_logs = inventory_logs[:25]
    req_logs = request_logs[:25]
    low_stock = counts["low_stock"]
    pending = [r for r in blood_requests_data if r["status"] == "Pending"]

    return render_template(
        "analytics.html",
        counts=counts,
        inv_logs=inv_logs,
        req_logs=req_logs,
        low_stock=low_stock,
        pending_requests=pending
    )


@app.route("/logout")
def logout():
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
