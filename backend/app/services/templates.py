"""Template gallery — pre-built starter templates for new projects.

Each template has vanilla and/or React variants with 4-6 files of
real UI code.  Templates are defined as dicts at module level so
they can be imported without a DB round-trip.
"""

from __future__ import annotations

# ── Landing Page (Vanilla) ─────────────────────────────────────

_LANDING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Landing Page</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <nav class="navbar">
    <div class="nav-container">
      <div class="logo">Brand</div>
      <button class="nav-toggle" aria-label="Menu">&#9776;</button>
      <ul class="nav-links">
        <li><a href="#hero">Home</a></li>
        <li><a href="#features">Features</a></li>
        <li><a href="#footer">Contact</a></li>
      </ul>
    </div>
  </nav>

  <section id="hero" class="hero">
    <div class="hero-content">
      <h1>Build Something Amazing</h1>
      <p>A modern platform for creators who want to move fast and ship beautiful products.</p>
      <div class="hero-actions">
        <a href="#features" class="btn btn-primary">Get Started</a>
        <a href="#features" class="btn btn-secondary">Learn More</a>
      </div>
    </div>
  </section>

  <section id="features" class="features">
    <h2>Why Choose Us</h2>
    <div class="features-grid">
      <div class="feature-card">
        <div class="feature-icon">&#9889;</div>
        <h3>Lightning Fast</h3>
        <p>Optimized for speed with instant page loads and smooth interactions.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">&#128274;</div>
        <h3>Secure by Default</h3>
        <p>Enterprise-grade security built into every layer of the platform.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">&#128640;</div>
        <h3>Scale Ready</h3>
        <p>Grows with your business from prototype to millions of users.</p>
      </div>
    </div>
  </section>

  <footer id="footer" class="footer">
    <p>&copy; 2026 Brand. All rights reserved.</p>
  </footer>
  <script src="script.js"></script>
</body>
</html>
"""

_LANDING_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: system-ui, -apple-system, sans-serif;
  color: #1a1a1a;
  background: #ffffff;
  line-height: 1.6;
}

.navbar {
  position: fixed;
  top: 0;
  width: 100%;
  background: rgba(255,255,255,0.95);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid #e5e7eb;
  z-index: 100;
}

.nav-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1rem 2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo { font-size: 1.25rem; font-weight: 700; }

.nav-links {
  list-style: none;
  display: flex;
  gap: 2rem;
}

.nav-links a {
  text-decoration: none;
  color: #555;
  font-size: 0.9rem;
  font-weight: 500;
  transition: color 0.2s;
}

.nav-links a:hover { color: #1a1a1a; }

.nav-toggle { display: none; background: none; border: none; font-size: 1.5rem; cursor: pointer; }

.hero {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6rem 2rem 4rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  text-align: center;
}

.hero-content { max-width: 700px; }

.hero h1 { font-size: 3rem; font-weight: 800; margin-bottom: 1rem; line-height: 1.2; }

.hero p { font-size: 1.125rem; opacity: 0.9; margin-bottom: 2rem; }

.hero-actions { display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }

.btn {
  display: inline-block;
  padding: 0.75rem 2rem;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.9rem;
  text-decoration: none;
  transition: transform 0.2s, box-shadow 0.2s;
}

.btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }

.btn-primary { background: white; color: #667eea; }

.btn-secondary { background: rgba(255,255,255,0.15); color: white; border: 1px solid rgba(255,255,255,0.3); }

.features { padding: 5rem 2rem; max-width: 1200px; margin: 0 auto; }

.features h2 { text-align: center; font-size: 2rem; margin-bottom: 3rem; }

.features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2rem; }

.feature-card {
  padding: 2rem;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  text-align: center;
  transition: box-shadow 0.2s;
}

.feature-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.08); }

.feature-icon { font-size: 2.5rem; margin-bottom: 1rem; }

.feature-card h3 { font-size: 1.125rem; margin-bottom: 0.5rem; }

.feature-card p { color: #666; font-size: 0.9rem; }

.footer { text-align: center; padding: 2rem; border-top: 1px solid #e5e7eb; color: #888; font-size: 0.875rem; }

@media (max-width: 768px) {
  .nav-links { display: none; position: absolute; top: 100%; left: 0; right: 0; background: white; flex-direction: column; padding: 1rem; border-bottom: 1px solid #e5e7eb; }
  .nav-links.open { display: flex; }
  .nav-toggle { display: block; }
  .hero h1 { font-size: 2rem; }
}
"""

_LANDING_JS = """\
document.querySelector('.nav-toggle')?.addEventListener('click', () => {
  document.querySelector('.nav-links')?.classList.toggle('open');
});
"""

# ── Dashboard (Vanilla) ────────────────────────────────────────

_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dashboard</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <div class="dashboard">
    <aside class="sidebar">
      <h2>MyApp</h2>
      <nav>
        <a href="#" class="active">&#128202; Dashboard</a>
        <a href="#">&#128196; Reports</a>
        <a href="#">&#128101; Users</a>
        <a href="#">&#9881; Settings</a>
      </nav>
    </aside>
    <main class="main">
      <header class="topbar">
        <h1>Dashboard</h1>
        <div class="user-badge">JD</div>
      </header>
      <section class="stats">
        <div class="stat-card">
          <span class="stat-label">Total Revenue</span>
          <span class="stat-value">$48,250</span>
          <span class="stat-change up">+12.5%</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Active Users</span>
          <span class="stat-value">2,847</span>
          <span class="stat-change up">+8.2%</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Orders</span>
          <span class="stat-value">1,423</span>
          <span class="stat-change down">-3.1%</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Conversion</span>
          <span class="stat-value">3.24%</span>
          <span class="stat-change up">+1.1%</span>
        </div>
      </section>
      <section class="table-section">
        <h2>Recent Orders</h2>
        <table>
          <thead><tr><th>Order</th><th>Customer</th><th>Status</th><th>Amount</th></tr></thead>
          <tbody>
            <tr><td>#1024</td><td>Alice Johnson</td><td><span class="badge success">Completed</span></td><td>$320</td></tr>
            <tr><td>#1025</td><td>Bob Smith</td><td><span class="badge warning">Pending</span></td><td>$180</td></tr>
            <tr><td>#1026</td><td>Carol White</td><td><span class="badge success">Completed</span></td><td>$450</td></tr>
            <tr><td>#1027</td><td>David Lee</td><td><span class="badge danger">Cancelled</span></td><td>$90</td></tr>
          </tbody>
        </table>
      </section>
    </main>
  </div>
  <script src="script.js"></script>
</body>
</html>
"""

_DASHBOARD_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: system-ui, -apple-system, sans-serif;
  background: #f3f4f6;
  color: #1a1a1a;
}

.dashboard { display: flex; min-height: 100vh; }

.sidebar {
  width: 250px;
  background: #1e293b;
  color: white;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.sidebar h2 { font-size: 1.25rem; font-weight: 700; }

.sidebar nav { display: flex; flex-direction: column; gap: 0.25rem; }

.sidebar nav a {
  color: #94a3b8;
  text-decoration: none;
  padding: 0.625rem 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
  transition: background 0.2s, color 0.2s;
}

.sidebar nav a:hover, .sidebar nav a.active { background: #334155; color: white; }

.main { flex: 1; padding: 1.5rem 2rem; }

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.topbar h1 { font-size: 1.5rem; font-weight: 700; }

.user-badge {
  width: 36px; height: 36px;
  border-radius: 50%;
  background: #667eea;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.8rem;
}

.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.stat-label { font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em; }

.stat-value { font-size: 1.5rem; font-weight: 700; }

.stat-change { font-size: 0.8rem; font-weight: 600; }
.stat-change.up { color: #22c55e; }
.stat-change.down { color: #ef4444; }

.table-section { background: white; border-radius: 12px; padding: 1.5rem; border: 1px solid #e5e7eb; }

.table-section h2 { font-size: 1.125rem; margin-bottom: 1rem; }

table { width: 100%; border-collapse: collapse; }

th, td { text-align: left; padding: 0.75rem 0.5rem; border-bottom: 1px solid #f3f4f6; font-size: 0.875rem; }

th { color: #888; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; }

.badge {
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge.success { background: #dcfce7; color: #16a34a; }
.badge.warning { background: #fef3c7; color: #d97706; }
.badge.danger { background: #fee2e2; color: #dc2626; }
"""

# ── Template Registry ──────────────────────────────────────────

TEMPLATES: dict[str, dict] = {
    "landing-page": {
        "name": "Landing Page",
        "description": "Hero section, features grid, responsive nav, and footer — great for products and startups.",
        "frameworks": ["vanilla"],
        "preview_snippet": "<h1>Landing Page</h1><p>Hero + features + footer</p>",
        "files": {
            "vanilla": [
                ("index.html", _LANDING_HTML, "html"),
                ("style.css", _LANDING_CSS, "css"),
                ("script.js", _LANDING_JS, "javascript"),
            ],
        },
    },
    "dashboard": {
        "name": "Dashboard",
        "description": "Sidebar layout with stats cards, data table, and status badges.",
        "frameworks": ["vanilla"],
        "preview_snippet": "<h1>Dashboard</h1><p>Sidebar + stats + table</p>",
        "files": {
            "vanilla": [
                ("index.html", _DASHBOARD_HTML, "html"),
                ("style.css", _DASHBOARD_CSS, "css"),
                ("script.js", _LANDING_JS, "javascript"),
            ],
        },
    },
}


def list_templates() -> list[dict]:
    """Return template metadata (without file contents) for the gallery browse endpoint."""
    result = []
    for tid, tmpl in TEMPLATES.items():
        result.append({
            "id": tid,
            "name": tmpl["name"],
            "description": tmpl["description"],
            "frameworks": tmpl["frameworks"],
            "preview_snippet": tmpl["preview_snippet"],
        })
    return result


def get_template_files(template_id: str, framework: str = "vanilla") -> list[tuple[str, str, str]] | None:
    """Return the file list for a template+framework, or None if not found."""
    tmpl = TEMPLATES.get(template_id)
    if tmpl is None:
        return None
    # Try requested framework, fall back to vanilla, then first available
    files = tmpl["files"].get(framework)
    if files is None:
        files = tmpl["files"].get("vanilla")
    if files is None and tmpl["files"]:
        files = next(iter(tmpl["files"].values()))
    return files
