from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, timezone
import os
from dotenv import load_dotenv 
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = "dev-secret"  # needed if you use flash()

# -------------------------
# Supabase setup
# -------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def sb_select(table: str, columns="*", **kwargs):
    q = supabase.table(table).select(columns)
    # allow ordering and limiting
    if "order" in kwargs:
        col, desc = kwargs["order"]
        q = q.order(col, desc=desc)
    if "limit" in kwargs:
        q = q.limit(kwargs["limit"])
    return q.execute().data

def sb_single(table: str, columns="*", **filters):
    q = supabase.table(table).select(columns)
    for k, v in filters.items():
        q = q.eq(k, v)
    data = q.limit(1).execute().data
    return data[0] if data else None

def summary_counts():
    users = sb_select("admin_users", "id,status")
    total_users = len(users)
    active_users = sum(1 for u in users if u.get("status") == "Active")
    suspended_users = total_users - active_users

    inv = sb_select("blood_inventory", "id,blood_type,quantity_ml")
    total_inventory_types = len(inv)
    total_inventory_ml = sum(int(i.get("quantity_ml") or 0) for i in inv)
    low_stock = [i for i in inv if int(i.get("quantity_ml") or 0) < 500]

    reqs = sb_select("blood_requests", "id,status")
    total_requests = len(reqs)
    pending_requests = sum(1 for r in reqs if r.get("status") == "Pending")
    approved_requests = sum(1 for r in reqs if r.get("status") == "Approved")
    fulfilled_requests = sum(1 for r in reqs if r.get("status") == "Fulfilled")

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
    supabase.table("inventory_logs").insert({
        "inventory_id": inventory_id,
        "action": action,
        "old_quantity": old_q,
        "new_quantity": new_q,
        "changed_by": changed_by,
        "changed_at": now_iso()
    }).execute()

def add_request_log(request_id, action, old_status, new_status, changed_by="Admin"):
    supabase.table("request_logs").insert({
        "request_id": request_id,
        "action": action,
        "old_status": old_status,
        "new_status": new_status,
        "changed_by": changed_by,
        "changed_at": now_iso()
    }).execute()


# -------------------------
# Routes (same as your existing app)
# -------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        role = request.form.get("role", "").strip()
        
        # Basic validation
        errors = []
        
        if not full_name:
            errors.append("Full name is required")
        if not email:
            errors.append("Email is required")
        if not password:
            errors.append("Password is required")
        if password != confirm_password:
            errors.append("Passwords do not match")
        if not role:
            errors.append("Please select a role")
        
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("register.html")
        
        try:
            # Insert user into database
            user_data = {
                "full_name": full_name,
                "email": email,
                "role": role,
                "status": "active",
                "created_at": now_iso()
            }
            
            # Add role-specific fields
            if role == "donor":
                user_data["blood_type"] = request.form.get("blood_type", "")
                user_data["age"] = request.form.get("age", None)
                user_data["medical_history"] = request.form.get("medical_history", "")
            elif role == "staff":
                user_data["hospital_name"] = request.form.get("hospital_name", "")
            
            # Insert into users table (you need to create this table)
            result = supabase.table("users").insert(user_data).execute()
            
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
            
        except Exception as e:
            flash(f"Registration failed: {str(e)}", "error")
            return render_template("register.html")
    
    return render_template("register.html")
    
@app.route("/dashboard")
def dashboard():
    counts = summary_counts()
    latest_inventory = sb_select("inventory_logs", "*", order=("changed_at", True), limit=5)
    latest_requests = sb_select("request_logs", "*", order=("changed_at", True), limit=5)
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
        if status not in ("Active", "Suspended"):
            status = "Active"

        if name and role:
            supabase.table("admin_users").insert({
                "name": name,
                "role": role,
                "status": status
            }).execute()
        return redirect(url_for("manage_users"))

    users = sb_select("admin_users", "*", order=("id", False))
    return render_template("manage_users.html", users=users)


@app.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    user = sb_single("admin_users", "*", id=user_id)
    if not user:
        return redirect(url_for("manage_users"))

    if request.method == "POST":
        name = request.form.get("name", user.get("name", "")).strip()
        role = request.form.get("role", user.get("role", "")).strip()
        status = request.form.get("status", user.get("status", "Active")).strip()
        if status not in ("Active", "Suspended"):
            status = user.get("status", "Active")

        supabase.table("admin_users").update({
            "name": name,
            "role": role,
            "status": status
        }).eq("id", user_id).execute()

        return redirect(url_for("manage_users"))

    return render_template("edit_user.html", user=user)


@app.route("/users/toggle/<int:user_id>")
def toggle_user(user_id):
    user = sb_single("admin_users", "id,status", id=user_id)
    if user:
        new_status = "Suspended" if user.get("status") == "Active" else "Active"
        supabase.table("admin_users").update({"status": new_status}).eq("id", user_id).execute()
    return redirect(url_for("manage_users"))


@app.route("/users/delete/<int:user_id>")
def delete_user(user_id):
    supabase.table("admin_users").delete().eq("id", user_id).execute()
    return redirect(url_for("manage_users"))


# ---- Blood Management (Inventory) ----
@app.route("/blood_management", methods=["GET", "POST"])
def blood_management():
    if request.method == "POST":
        action = request.form.get("action")
        item_id = int(request.form.get("id"))
        qty = int(request.form.get("quantity_ml"))

        item = sb_single("blood_inventory", "*", id=item_id)
        if item:
            old_q = int(item.get("quantity_ml") or 0)

            if action == "set":
                new_q = max(0, qty)
                supabase.table("blood_inventory").update({
                    "quantity_ml": new_q,
                    "updated_at": now_iso()
                }).eq("id", item_id).execute()
                add_inventory_log(item_id, "UPDATE", old_q, new_q)

            elif action == "add":
                new_q = old_q + max(0, qty)
                supabase.table("blood_inventory").update({
                    "quantity_ml": new_q,
                    "updated_at": now_iso()
                }).eq("id", item_id).execute()
                add_inventory_log(item_id, "ADD", old_q, new_q)

            elif action == "remove":
                new_q = max(0, old_q - max(0, qty))
                supabase.table("blood_inventory").update({
                    "quantity_ml": new_q,
                    "updated_at": now_iso()
                }).eq("id", item_id).execute()
                add_inventory_log(item_id, "REMOVE", old_q, new_q)

        return redirect(url_for("blood_management"))

    inventory = sb_select("blood_inventory", "*", order=("blood_type", False))
    low_stock = [i for i in inventory if int(i.get("quantity_ml") or 0) < 500]
    return render_template("blood_management.html", inventory=inventory, low_stock=low_stock)


# ---- Blood Requests ----
@app.route("/blood_requests", methods=["GET", "POST"])
def blood_requests():
    if request.method == "POST":
        requester = request.form.get("requester", "").strip()
        blood_type = request.form.get("blood_type", "").strip()
        quantity_ml = int(request.form.get("quantity_ml", "0"))

        if requester and blood_type and quantity_ml > 0:
            inserted = supabase.table("blood_requests").insert({
                "requester": requester,
                "blood_type": blood_type,
                "quantity_ml": quantity_ml,
                "status": "Pending"
            }).execute().data

            # get new id for logging
            new_id = inserted[0]["id"] if inserted else None
            if new_id:
                add_request_log(new_id, "CREATE", "-", "Pending")

        return redirect(url_for("blood_requests"))

    requests_list = sb_select("blood_requests", "*", order=("created_at", True))
    return render_template("blood_requests.html", requests=requests_list)


@app.route("/requests/status/<int:req_id>/<new_status>")
def update_request_status(req_id, new_status):
    if new_status not in ("Pending", "Approved", "Fulfilled"):
        return redirect(url_for("blood_requests"))

    req = sb_single("blood_requests", "id,status", id=req_id)
    if req:
        old = req.get("status")
        supabase.table("blood_requests").update({"status": new_status}).eq("id", req_id).execute()
        add_request_log(req_id, "STATUS", old, new_status)

    return redirect(url_for("blood_requests"))


@app.route("/requests/delete/<int:req_id>")
def delete_request(req_id):
    supabase.table("blood_requests").delete().eq("id", req_id).execute()
    add_request_log(req_id, "DELETE", "-", "-")
    return redirect(url_for("blood_requests"))


# ---- Analytics ----
@app.route("/analytics")
def analytics():
    counts = summary_counts()
    inv_logs = sb_select("inventory_logs", "*", order=("changed_at", True), limit=25)
    req_logs = sb_select("request_logs", "*", order=("changed_at", True), limit=25)
    low_stock = counts["low_stock"]

    pending_requests = supabase.table("blood_requests").select("*").eq("status", "Pending").execute().data

    return render_template(
        "analytics.html",
        counts=counts,
        inv_logs=inv_logs,
        req_logs=req_logs,
        low_stock=low_stock,
        pending_requests=pending_requests
    )


@app.route("/logout")
def logout():
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
