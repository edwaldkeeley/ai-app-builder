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

# ── Portfolio (Vanilla) ─────────────────────────────────────────

_PORTFOLIO_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Portfolio</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <nav class="navbar">
    <div class="nav-container">
      <div class="logo">Alex Rivera</div>
      <button class="nav-toggle" aria-label="Menu">&#9776;</button>
      <ul class="nav-links">
        <li><a href="#work">Work</a></li>
        <li><a href="#about">About</a></li>
        <li><a href="#contact">Contact</a></li>
      </ul>
    </div>
  </nav>

  <section id="hero" class="hero">
    <div class="hero-content">
      <p class="hero-tag">Design &amp; Code</p>
      <h1>I build digital experiences that people love.</h1>
      <p>Full-stack designer &amp; developer specializing in web apps and interactive design.</p>
      <div class="hero-actions">
        <a href="#work" class="btn btn-primary">View Projects</a>
        <a href="#contact" class="btn btn-secondary">Get in Touch</a>
      </div>
    </div>
  </section>

  <section id="work" class="work">
    <h2>Selected Work</h2>
    <div class="work-grid">
      <div class="work-card">
        <div class="work-card-img" style="background:#667eea;">&nbsp;</div>
        <div class="work-card-body">
          <span class="work-tag">Web App</span>
          <h3>Flow Dashboard</h3>
          <p>Analytics dashboard with real-time data visualization and team collaboration tools.</p>
        </div>
      </div>
      <div class="work-card">
        <div class="work-card-img" style="background:#e86f6f;">&nbsp;</div>
        <div class="work-card-body">
          <span class="work-tag">E-commerce</span>
          <h3>Marketplace</h3>
          <p>A modern marketplace platform with smart search, filters, and seamless checkout.</p>
        </div>
      </div>
      <div class="work-card">
        <div class="work-card-img" style="background:#4ecdc4;">&nbsp;</div>
        <div class="work-card-body">
          <span class="work-tag">Mobile</span>
          <h3>Weather App</h3>
          <p>Minimal weather app with location-based forecasts and beautiful animations.</p>
        </div>
      </div>
    </div>
  </section>

  <section id="about" class="about">
    <div class="about-content">
      <h2>About Me</h2>
      <p>I'm a designer and developer with 8+ years of experience building products for startups and enterprise clients. I focus on creating interfaces that are both beautiful and functional.</p>
      <div class="about-stats">
        <div class="about-stat"><strong>50+</strong> Projects</div>
        <div class="about-stat"><strong>30+</strong> Clients</div>
        <div class="about-stat"><strong>12</strong> Awards</div>
      </div>
    </div>
  </section>

  <section id="contact" class="contact">
    <h2>Let&#8217;s work together</h2>
    <p>Have a project in mind? Let's talk about it.</p>
    <a href="mailto:hello@alexrivera.dev" class="btn btn-primary">hello@alexrivera.dev</a>
  </section>

  <footer class="footer">
    <p>&copy; 2026 Alex Rivera. All rights reserved.</p>
  </footer>
  <script src="script.js"></script>
</body>
</html>
"""

_PORTFOLIO_CSS = """\
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

.nav-container { max-width: 1200px; margin: 0 auto; padding: 1rem 2rem; display: flex; align-items: center; justify-content: space-between; }
.logo { font-size: 1.25rem; font-weight: 700; }
.nav-links { list-style: none; display: flex; gap: 2rem; }
.nav-links a { text-decoration: none; color: #555; font-size: 0.9rem; font-weight: 500; transition: color 0.2s; }
.nav-links a:hover { color: #1a1a1a; }
.nav-toggle { display: none; background: none; border: none; font-size: 1.5rem; cursor: pointer; }

.hero {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6rem 2rem 4rem;
  background: #f8f9fa;
  text-align: center;
}
.hero-content { max-width: 700px; }
.hero-tag { font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.15em; color: #667eea; font-weight: 600; margin-bottom: 0.75rem; }
.hero h1 { font-size: 3rem; font-weight: 800; margin-bottom: 1rem; line-height: 1.2; color: #111; }
.hero p { font-size: 1.125rem; color: #666; margin-bottom: 2rem; max-width: 500px; margin-left: auto; margin-right: auto; }

.btn {
  display: inline-block; padding: 0.75rem 2rem; border-radius: 8px; font-weight: 600;
  font-size: 0.9rem; text-decoration: none; transition: transform 0.2s, box-shadow 0.2s;
}
.btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.btn-primary { background: #1a1a1a; color: white; }
.btn-secondary { background: transparent; color: #1a1a1a; border: 1px solid #d1d5db; }

.work { padding: 5rem 2rem; max-width: 1200px; margin: 0 auto; }
.work h2 { text-align: center; font-size: 2rem; margin-bottom: 3rem; }
.work-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2rem; }
.work-card { border-radius: 12px; border: 1px solid #e5e7eb; overflow: hidden; transition: box-shadow 0.2s; }
.work-card:hover { box-shadow: 0 8px 25px rgba(0,0,0,0.08); }
.work-card-img { height: 200px; }
.work-card-body { padding: 1.5rem; }
.work-tag { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; color: #667eea; font-weight: 600; }
.work-card-body h3 { font-size: 1.125rem; margin: 0.5rem 0; }
.work-card-body p { color: #666; font-size: 0.9rem; }

.about { padding: 5rem 2rem; background: #f8f9fa; }
.about-content { max-width: 700px; margin: 0 auto; text-align: center; }
.about-content h2 { font-size: 2rem; margin-bottom: 1rem; }
.about-content p { color: #666; font-size: 1rem; margin-bottom: 2rem; }
.about-stats { display: flex; justify-content: center; gap: 3rem; }
.about-stat { text-align: center; }
.about-stat strong { display: block; font-size: 2rem; color: #111; }

.contact { padding: 5rem 2rem; text-align: center; background: #1a1a1a; color: white; }
.contact h2 { font-size: 2rem; margin-bottom: 0.75rem; }
.contact p { color: #aaa; margin-bottom: 2rem; }
.contact .btn-primary { background: white; color: #1a1a1a; }

.footer { text-align: center; padding: 2rem; background: #111; color: #888; font-size: 0.875rem; }

@media (max-width: 768px) {
  .nav-links { display: none; position: absolute; top: 100%; left: 0; right: 0; background: white; flex-direction: column; padding: 1rem; border-bottom: 1px solid #e5e7eb; }
  .nav-links.open { display: flex; }
  .nav-toggle { display: block; }
  .hero h1 { font-size: 2rem; }
  .about-stats { flex-direction: column; gap: 1.5rem; }
}
"""

# ── Portfolio (React) ────────────────────────────────────────────

_PORTFOLIO_REACT_APP = """\
import React, { useState } from "react";
import { createRoot } from "react-dom/client";

function Header() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="navbar">
      <div className="nav-container">
        <div className="logo">Alex Rivera</div>
        <button className="nav-toggle" aria-label="Menu" onClick={() => setMenuOpen((p) => !p)}>
          &#9776;
        </button>
        <ul className={"nav-links" + (menuOpen ? " open" : "")}>
          <li><a href="#work" onClick={() => setMenuOpen(false)}>Work</a></li>
          <li><a href="#about" onClick={() => setMenuOpen(false)}>About</a></li>
          <li><a href="#contact" onClick={() => setMenuOpen(false)}>Contact</a></li>
        </ul>
      </div>
    </nav>
  );
}

function Hero() {
  return (
    <section id="hero" className="hero">
      <div className="hero-content">
        <p className="hero-tag">Design &amp; Code</p>
        <h1>I build digital experiences that people love.</h1>
        <p>Full-stack designer &amp; developer specializing in web apps and interactive design.</p>
        <div className="hero-actions">
          <a href="#work" className="btn btn-primary">View Projects</a>
          <a href="#contact" className="btn btn-secondary">Get in Touch</a>
        </div>
      </div>
    </section>
  );
}

const projects = [
  { tag: "Web App", title: "Flow Dashboard", desc: "Analytics dashboard with real-time data visualization and team collaboration tools.", color: "#667eea" },
  { tag: "E-commerce", title: "Marketplace", desc: "A modern marketplace platform with smart search, filters, and seamless checkout.", color: "#e86f6f" },
  { tag: "Mobile", title: "Weather App", desc: "Minimal weather app with location-based forecasts and beautiful animations.", color: "#4ecdc4" },
];

function Work() {
  return (
    <section id="work" className="work">
      <h2>Selected Work</h2>
      <div className="work-grid">
        {projects.map((p, i) => (
          <div className="work-card" key={i}>
            <div className="work-card-img" style={{ background: p.color }}>&nbsp;</div>
            <div className="work-card-body">
              <span className="work-tag">{p.tag}</span>
              <h3>{p.title}</h3>
              <p>{p.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function About() {
  return (
    <section id="about" className="about">
      <div className="about-content">
        <h2>About Me</h2>
        <p>I'm a designer and developer with 8+ years of experience building products for startups and enterprise clients. I focus on creating interfaces that are both beautiful and functional.</p>
        <div className="about-stats">
          <div className="about-stat"><strong>50+</strong> Projects</div>
          <div className="about-stat"><strong>30+</strong> Clients</div>
          <div className="about-stat"><strong>12</strong> Awards</div>
        </div>
      </div>
    </section>
  );
}

function Contact() {
  return (
    <section id="contact" className="contact">
      <h2>Let&#8217;s work together</h2>
      <p>Have a project in mind? Let's talk about it.</p>
      <a href="mailto:hello@alexrivera.dev" className="btn btn-primary">hello@alexrivera.dev</a>
    </section>
  );
}

function App() {
  return (
    <>
      <Header />
      <Hero />
      <Work />
      <About />
      <Contact />
      <footer className="footer">
        <p>&copy; 2026 Alex Rivera. All rights reserved.</p>
      </footer>
    </>
  );
}

const root = createRoot(document.getElementById("root"));
root.render(<App />);
"""

# ── Blog (Vanilla) ──────────────────────────────────────────────

_BLOG_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Blog</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <nav class="navbar">
    <div class="nav-container">
      <div class="logo">The Daily Byte</div>
      <button class="nav-toggle" aria-label="Menu">&#9776;</button>
      <ul class="nav-links">
        <li><a href="#articles" class="active">Articles</a></li>
        <li><a href="#">Topics</a></li>
        <li><a href="#">About</a></li>
      </ul>
    </div>
  </nav>

  <header class="blog-header">
    <h1>Thoughts on design, code, and product.</h1>
    <p>Exploring the intersection of technology and creativity.</p>
  </header>

  <main id="articles" class="articles">
    <article class="article-card">
      <div class="article-meta">
        <span class="article-category">Design</span>
        <span class="article-date">Aug 15, 2026</span>
      </div>
      <h2><a href="#">Building a Design System from Scratch</a></h2>
      <p>A practical guide to creating a scalable design system that your team will actually use.</p>
      <div class="article-footer">
        <span class="article-author">By Sarah Chen</span>
        <span class="article-read">8 min read</span>
      </div>
    </article>

    <article class="article-card">
      <div class="article-meta">
        <span class="article-category">Engineering</span>
        <span class="article-date">Aug 10, 2026</span>
      </div>
      <h2><a href="#">The State of Web Performance in 2026</a></h2>
      <p>New metrics, tools, and techniques for keeping your web apps fast and responsive.</p>
      <div class="article-footer">
        <span class="article-author">By Marcus Johnson</span>
        <span class="article-read">12 min read</span>
      </div>
    </article>

    <article class="article-card">
      <div class="article-meta">
        <span class="article-category">Product</span>
        <span class="article-date">Aug 5, 2026</span>
      </div>
      <h2><a href="#">Why MVPs Still Matter</a></h2>
      <p>How to ship a minimum viable product that validates your ideas without cutting corners.</p>
      <div class="article-footer">
        <span class="article-author">By Priya Patel</span>
        <span class="article-read">6 min read</span>
      </div>
    </article>

    <article class="article-card">
      <div class="article-meta">
        <span class="article-category">Design</span>
        <span class="article-date">Jul 28, 2026</span>
      </div>
      <h2><a href="#">Accessibility-First Design Patterns</a></h2>
      <p>Inclusive design patterns that make your products better for everyone.</p>
      <div class="article-footer">
        <span class="article-author">By Alex Rivera</span>
        <span class="article-read">10 min read</span>
      </div>
    </article>
  </main>

  <aside class="newsletter">
    <div class="newsletter-content">
      <h2>Stay updated</h2>
      <p>Get the latest articles delivered to your inbox weekly.</p>
      <form class="newsletter-form" onsubmit="event.preventDefault(); alert('Thanks for subscribing!');">
        <input type="email" placeholder="Enter your email" required aria-label="Email address" />
        <button type="submit">Subscribe</button>
      </form>
    </div>
  </aside>

  <footer class="footer">
    <p>&copy; 2026 The Daily Byte. All rights reserved.</p>
  </footer>
  <script src="script.js"></script>
</body>
</html>
"""

_BLOG_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: Georgia, "Times New Roman", serif;
  color: #1a1a1a;
  background: #fafafa;
  line-height: 1.7;
}

.navbar {
  position: fixed; top: 0; width: 100%;
  background: rgba(255,255,255,0.95); backdrop-filter: blur(8px);
  border-bottom: 1px solid #e5e7eb; z-index: 100;
}
.nav-container { max-width: 800px; margin: 0 auto; padding: 1rem 2rem; display: flex; align-items: center; justify-content: space-between; }
.logo { font-size: 1.125rem; font-weight: 700; font-family: system-ui, -apple-system, sans-serif; }
.nav-links { list-style: none; display: flex; gap: 1.5rem; }
.nav-links a { text-decoration: none; color: #666; font-size: 0.875rem; font-family: system-ui, -apple-system, sans-serif; transition: color 0.2s; }
.nav-links a:hover, .nav-links a.active { color: #1a1a1a; }
.nav-toggle { display: none; background: none; border: none; font-size: 1.5rem; cursor: pointer; }

.blog-header { padding: 8rem 2rem 4rem; text-align: center; max-width: 700px; margin: 0 auto; }
.blog-header h1 { font-size: 2.5rem; font-weight: 700; line-height: 1.3; margin-bottom: 0.75rem; }
.blog-header p { font-size: 1.125rem; color: #666; }

.articles { max-width: 700px; margin: 0 auto; padding: 0 2rem 4rem; }

.article-card {
  padding: 2rem 0;
  border-bottom: 1px solid #e5e7eb;
}
.article-card:last-child { border-bottom: none; }

.article-meta { display: flex; gap: 1rem; align-items: center; margin-bottom: 0.5rem; font-family: system-ui, -apple-system, sans-serif; }
.article-category { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; color: #667eea; font-weight: 600; }
.article-date { font-size: 0.8rem; color: #999; }

.article-card h2 { font-size: 1.5rem; margin-bottom: 0.5rem; }
.article-card h2 a { color: #1a1a1a; text-decoration: none; transition: color 0.2s; }
.article-card h2 a:hover { color: #667eea; }
.article-card p { color: #555; font-size: 1rem; }

.article-footer { display: flex; gap: 1.5rem; margin-top: 1rem; font-family: system-ui, -apple-system, sans-serif; font-size: 0.8rem; color: #999; }

.newsletter {
  background: #1a1a1a; color: white; padding: 4rem 2rem; text-align: center;
}
.newsletter-content { max-width: 450px; margin: 0 auto; }
.newsletter h2 { font-size: 1.5rem; margin-bottom: 0.5rem; font-family: system-ui, -apple-system, sans-serif; }
.newsletter p { color: #aaa; font-size: 0.9rem; margin-bottom: 1.5rem; }
.newsletter-form { display: flex; gap: 0.5rem; justify-content: center; }
.newsletter-form input {
  flex: 1; padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #333;
  background: #222; color: white; font-size: 0.9rem; font-family: system-ui, -apple-system, sans-serif;
}
.newsletter-form button {
  padding: 0.75rem 1.5rem; border-radius: 8px; border: none;
  background: white; color: #1a1a1a; font-weight: 600; cursor: pointer; font-size: 0.9rem;
  transition: opacity 0.2s;
}
.newsletter-form button:hover { opacity: 0.9; }

.footer { text-align: center; padding: 2rem; color: #999; font-size: 0.8rem; font-family: system-ui, -apple-system, sans-serif; }

@media (max-width: 768px) {
  .nav-links { display: none; position: absolute; top: 100%; left: 0; right: 0; background: white; flex-direction: column; padding: 1rem; border-bottom: 1px solid #e5e7eb; }
  .nav-links.open { display: flex; }
  .nav-toggle { display: block; }
  .blog-header h1 { font-size: 1.75rem; }
  .newsletter-form { flex-direction: column; }
}
"""

_BLOG_JS = """\
document.querySelector('.nav-toggle')?.addEventListener('click', () => {
  document.querySelector('.nav-links')?.classList.toggle('open');
});
"""

# ── Blog (React) ────────────────────────────────────────────────

_BLOG_REACT_APP = """\
import React, { useState } from "react";
import { createRoot } from "react-dom/client";

function Header() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="navbar">
      <div className="nav-container">
        <div className="logo">The Daily Byte</div>
        <button className="nav-toggle" aria-label="Menu" onClick={() => setMenuOpen((p) => !p)}>
          &#9776;
        </button>
        <ul className={"nav-links" + (menuOpen ? " open" : "")}>
          <li><a href="#articles" className="active" onClick={() => setMenuOpen(false)}>Articles</a></li>
          <li><a href="#" onClick={() => setMenuOpen(false)}>Topics</a></li>
          <li><a href="#" onClick={() => setMenuOpen(false)}>About</a></li>
        </ul>
      </div>
    </nav>
  );
}

const articles = [
  { category: "Design", date: "Aug 15, 2026", title: "Building a Design System from Scratch", desc: "A practical guide to creating a scalable design system that your team will actually use.", author: "Sarah Chen", read: "8 min read" },
  { category: "Engineering", date: "Aug 10, 2026", title: "The State of Web Performance in 2026", desc: "New metrics, tools, and techniques for keeping your web apps fast and responsive.", author: "Marcus Johnson", read: "12 min read" },
  { category: "Product", date: "Aug 5, 2026", title: "Why MVPs Still Matter", desc: "How to ship a minimum viable product that validates your ideas without cutting corners.", author: "Priya Patel", read: "6 min read" },
  { category: "Design", date: "Jul 28, 2026", title: "Accessibility-First Design Patterns", desc: "Inclusive design patterns that make your products better for everyone.", author: "Alex Rivera", read: "10 min read" },
];

function ArticleCard({ article }) {
  return (
    <article className="article-card">
      <div className="article-meta">
        <span className="article-category">{article.category}</span>
        <span className="article-date">{article.date}</span>
      </div>
      <h2><a href="#">{article.title}</a></h2>
      <p>{article.desc}</p>
      <div className="article-footer">
        <span className="article-author">By {article.author}</span>
        <span className="article-read">{article.read}</span>
      </div>
    </article>
  );
}

function Newsletter() {
  const [email, setEmail] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    alert("Thanks for subscribing!");
    setEmail("");
  };

  return (
    <aside className="newsletter">
      <div className="newsletter-content">
        <h2>Stay updated</h2>
        <p>Get the latest articles delivered to your inbox weekly.</p>
        <form className="newsletter-form" onSubmit={handleSubmit}>
          <input type="email" placeholder="Enter your email" required aria-label="Email address" value={email} onChange={(e) => setEmail(e.target.value)} />
          <button type="submit">Subscribe</button>
        </form>
      </div>
    </aside>
  );
}

function App() {
  return (
    <>
      <Header />
      <header className="blog-header">
        <h1>Thoughts on design, code, and product.</h1>
        <p>Exploring the intersection of technology and creativity.</p>
      </header>
      <main id="articles" className="articles">
        {articles.map((a, i) => <ArticleCard article={a} key={i} />)}
      </main>
      <Newsletter />
      <footer className="footer">
        <p>&copy; 2026 The Daily Byte. All rights reserved.</p>
      </footer>
    </>
  );
}

const root = createRoot(document.getElementById("root"));
root.render(<App />);
"""

# ── Pricing (Vanilla) ──────────────────────────────────────────

_PRICING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Pricing</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <nav class="navbar">
    <div class="nav-container">
      <div class="logo">SaaSify</div>
      <button class="nav-toggle" aria-label="Menu">&#9776;</button>
      <ul class="nav-links">
        <li><a href="#pricing">Pricing</a></li>
        <li><a href="#features">Features</a></li>
        <li><a href="#faq">FAQ</a></li>
      </ul>
    </div>
  </nav>

  <header class="pricing-header">
    <h1>Simple, transparent pricing</h1>
    <p>No hidden fees. No surprises. Upgrade or cancel anytime.</p>
    <div class="billing-toggle">
      <span class="toggle-label active">Monthly</span>
      <label class="toggle-switch">
        <input type="checkbox" id="billingToggle" />
        <span class="toggle-slider"></span>
      </label>
      <span class="toggle-label">Yearly <span class="toggle-badge">Save 20%</span></span>
    </div>
  </header>

  <section id="pricing" class="pricing-grid">
    <div class="pricing-card">
      <h3>Starter</h3>
      <div class="price"><span class="price-amount" data-monthly="19" data-yearly="15">$19</span> <span class="price-period">/month</span></div>
      <p class="price-desc">Perfect for individuals and side projects.</p>
      <ul class="price-features">
        <li>&#10003; 5 projects</li>
        <li>&#10003; 10GB storage</li>
        <li>&#10003; Basic analytics</li>
        <li>&#10003; Email support</li>
      </ul>
      <a href="#" class="btn btn-secondary">Get Started</a>
    </div>

    <div class="pricing-card featured">
      <div class="featured-badge">Most Popular</div>
      <h3>Professional</h3>
      <div class="price"><span class="price-amount" data-monthly="49" data-yearly="39">$49</span> <span class="price-period">/month</span></div>
      <p class="price-desc">For growing teams and businesses.</p>
      <ul class="price-features">
        <li>&#10003; Unlimited projects</li>
        <li>&#10003; 100GB storage</li>
        <li>&#10003; Advanced analytics</li>
        <li>&#10003; Priority support</li>
        <li>&#10003; Custom domains</li>
      </ul>
      <a href="#" class="btn btn-primary">Get Started</a>
    </div>

    <div class="pricing-card">
      <h3>Enterprise</h3>
      <div class="price"><span class="price-amount" data-monthly="99" data-yearly="79">$99</span> <span class="price-period">/month</span></div>
      <p class="price-desc">For large organizations with advanced needs.</p>
      <ul class="price-features">
        <li>&#10003; Everything in Professional</li>
        <li>&#10003; Unlimited storage</li>
        <li>&#10003; Custom integrations</li>
        <li>&#10003; 24/7 phone support</li>
        <li>&#10003; SLA guarantee</li>
        <li>&#10003; Dedicated account manager</li>
      </ul>
      <a href="#" class="btn btn-secondary">Contact Sales</a>
    </div>
  </section>

  <section id="faq" class="faq">
    <h2>Frequently asked questions</h2>
    <div class="faq-list">
      <details>
        <summary>Can I change my plan later?</summary>
        <p>Yes, you can upgrade or downgrade at any time. Changes take effect immediately.</p>
      </details>
      <details>
        <summary>Is there a free trial?</summary>
        <p>Yes, all plans come with a 14-day free trial. No credit card required.</p>
      </details>
      <details>
        <summary>What payment methods do you accept?</summary>
        <p>We accept all major credit cards, PayPal, and wire transfers for enterprise plans.</p>
      </details>
    </div>
  </section>

  <footer class="footer">
    <p>&copy; 2026 SaaSify. All rights reserved.</p>
  </footer>
  <script src="script.js"></script>
</body>
</html>
"""

_PRICING_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: system-ui, -apple-system, sans-serif;
  color: #1a1a1a;
  background: #ffffff;
  line-height: 1.6;
}

.navbar {
  position: fixed; top: 0; width: 100%;
  background: rgba(255,255,255,0.95); backdrop-filter: blur(8px);
  border-bottom: 1px solid #e5e7eb; z-index: 100;
}
.nav-container { max-width: 1200px; margin: 0 auto; padding: 1rem 2rem; display: flex; align-items: center; justify-content: space-between; }
.logo { font-size: 1.25rem; font-weight: 700; }
.nav-links { list-style: none; display: flex; gap: 2rem; }
.nav-links a { text-decoration: none; color: #555; font-size: 0.9rem; font-weight: 500; transition: color 0.2s; }
.nav-links a:hover { color: #1a1a1a; }
.nav-toggle { display: none; background: none; border: none; font-size: 1.5rem; cursor: pointer; }

.pricing-header { padding: 8rem 2rem 3rem; text-align: center; }
.pricing-header h1 { font-size: 2.5rem; font-weight: 800; margin-bottom: 0.5rem; }
.pricing-header p { color: #666; font-size: 1.125rem; margin-bottom: 2rem; }

.billing-toggle { display: flex; align-items: center; justify-content: center; gap: 0.75rem; }
.toggle-label { font-size: 0.9rem; color: #888; font-weight: 500; }
.toggle-label.active { color: #1a1a1a; }
.toggle-badge { font-size: 0.75rem; background: #dcfce7; color: #16a34a; padding: 0.15rem 0.5rem; border-radius: 999px; font-weight: 600; }
.toggle-switch { position: relative; display: inline-block; width: 44px; height: 24px; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute; cursor: pointer; inset: 0; border-radius: 24px; background: #d1d5db;
  transition: background 0.3s;
}
.toggle-slider::before {
  content: ""; position: absolute; left: 3px; bottom: 3px; width: 18px; height: 18px;
  border-radius: 50%; background: white; transition: transform 0.3s;
}
.toggle-switch input:checked + .toggle-slider { background: #667eea; }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(20px); }

.pricing-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 2rem; max-width: 1000px; margin: 0 auto; padding: 0 2rem 4rem;
}

.pricing-card {
  padding: 2rem; border-radius: 16px; border: 1px solid #e5e7eb;
  display: flex; flex-direction: column; gap: 1.25rem; position: relative;
  transition: box-shadow 0.2s;
}
.pricing-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.06); }
.pricing-card.featured { border-color: #667eea; box-shadow: 0 4px 20px rgba(102,126,234,0.1); }
.featured-badge {
  position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
  background: #667eea; color: white; font-size: 0.75rem; font-weight: 600;
  padding: 0.25rem 1rem; border-radius: 999px;
}

.pricing-card h3 { font-size: 1.125rem; }
.price { display: flex; align-items: baseline; gap: 0.25rem; }
.price-amount { font-size: 2.5rem; font-weight: 800; }
.price-period { color: #888; font-size: 0.9rem; }
.price-desc { color: #666; font-size: 0.875rem; }

.price-features { list-style: none; display: flex; flex-direction: column; gap: 0.75rem; flex: 1; }
.price-features li { font-size: 0.9rem; color: #444; }

.btn {
  display: inline-block; padding: 0.75rem 2rem; border-radius: 8px; font-weight: 600;
  font-size: 0.9rem; text-decoration: none; text-align: center; transition: transform 0.2s, box-shadow 0.2s;
}
.btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.btn-primary { background: #667eea; color: white; }
.btn-secondary { background: transparent; color: #1a1a1a; border: 1px solid #d1d5db; }

.faq { padding: 4rem 2rem 5rem; max-width: 700px; margin: 0 auto; }
.faq h2 { text-align: center; font-size: 1.5rem; margin-bottom: 2rem; }
.faq-list { display: flex; flex-direction: column; gap: 0.75rem; }
details { padding: 1rem 1.25rem; border-radius: 12px; border: 1px solid #e5e7eb; cursor: pointer; }
summary { font-weight: 600; font-size: 0.9rem; }
details p { margin-top: 0.75rem; color: #666; font-size: 0.875rem; }

.footer { text-align: center; padding: 2rem; color: #888; font-size: 0.875rem; border-top: 1px solid #e5e7eb; }

@media (max-width: 768px) {
  .nav-links { display: none; position: absolute; top: 100%; left: 0; right: 0; background: white; flex-direction: column; padding: 1rem; border-bottom: 1px solid #e5e7eb; }
  .nav-links.open { display: flex; }
  .nav-toggle { display: block; }
  .pricing-header h1 { font-size: 1.75rem; }
  .pricing-grid { grid-template-columns: 1fr; }
}
"""

_PRICING_JS = """\
document.querySelector('.nav-toggle')?.addEventListener('click', () => {
  document.querySelector('.nav-links')?.classList.toggle('open');
});

const toggle = document.getElementById('billingToggle');
toggle?.addEventListener('change', () => {
  const yearly = toggle.checked;
  document.querySelectorAll('.price-amount').forEach(el => {
    const monthly = el.dataset.monthly;
    const annual = el.dataset.yearly;
    el.textContent = yearly && annual ? '$' + annual : '$' + monthly;
  });
  document.querySelectorAll('.toggle-label').forEach(l => l.classList.remove('active'));
  if (yearly) {
    toggle.closest('.billing-toggle')?.querySelector('.toggle-label:last-child')?.classList.add('active');
  } else {
    toggle.closest('.billing-toggle')?.querySelector('.toggle-label:first-child')?.classList.add('active');
  }
});
"""

# ── Pricing (React) ──────────────────────────────────────────

_PRICING_REACT_APP = """\
import React, { useState } from "react";
import { createRoot } from "react-dom/client";

const plans = [
  { name: "Starter", monthly: 19, yearly: 15, desc: "Perfect for individuals and side projects.", features: ["5 projects", "10GB storage", "Basic analytics", "Email support"], cta: "Get Started", featured: false },
  { name: "Professional", monthly: 49, yearly: 39, desc: "For growing teams and businesses.", features: ["Unlimited projects", "100GB storage", "Advanced analytics", "Priority support", "Custom domains"], cta: "Get Started", featured: true },
  { name: "Enterprise", monthly: 99, yearly: 79, desc: "For large organizations with advanced needs.", features: ["Everything in Professional", "Unlimited storage", "Custom integrations", "24/7 phone support", "SLA guarantee", "Dedicated account manager"], cta: "Contact Sales", featured: false },
];

function Header() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="navbar">
      <div className="nav-container">
        <div className="logo">SaaSify</div>
        <button className="nav-toggle" aria-label="Menu" onClick={() => setMenuOpen((p) => !p)}>
          &#9776;
        </button>
        <ul className={"nav-links" + (menuOpen ? " open" : "")}>
          <li><a href="#pricing" onClick={() => setMenuOpen(false)}>Pricing</a></li>
          <li><a href="#features" onClick={() => setMenuOpen(false)}>Features</a></li>
          <li><a href="#faq" onClick={() => setMenuOpen(false)}>FAQ</a></li>
        </ul>
      </div>
    </nav>
  );
}

function PricingCard({ plan, yearly }) {
  const amount = yearly ? plan.yearly : plan.monthly;
  return (
    <div className={"pricing-card" + (plan.featured ? " featured" : "")}>
      {plan.featured && <div className="featured-badge">Most Popular</div>}
      <h3>{plan.name}</h3>
      <div className="price"><span className="price-amount">${amount}</span> <span className="price-period">/month</span></div>
      <p className="price-desc">{plan.desc}</p>
      <ul className="price-features">
        {plan.features.map((f, i) => <li key={i}>&#10003; {f}</li>)}
      </ul>
      <a href="#" className={"btn " + (plan.featured ? "btn-primary" : "btn-secondary")}>{plan.cta}</a>
    </div>
  );
}

function FAQ() {
  const [open, setOpen] = useState(null);

  const faqs = [
    { q: "Can I change my plan later?", a: "Yes, you can upgrade or downgrade at any time. Changes take effect immediately." },
    { q: "Is there a free trial?", a: "Yes, all plans come with a 14-day free trial. No credit card required." },
    { q: "What payment methods do you accept?", a: "We accept all major credit cards, PayPal, and wire transfers for enterprise plans." },
  ];

  return (
    <section id="faq" className="faq">
      <h2>Frequently asked questions</h2>
      <div className="faq-list">
        {faqs.map((faq, i) => (
          <details key={i} open={open === i} onClick={() => setOpen(open === i ? null : i)}>
            <summary>{faq.q}</summary>
            <p>{faq.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function App() {
  const [yearly, setYearly] = useState(false);

  return (
    <>
      <Header />
      <header className="pricing-header">
        <h1>Simple, transparent pricing</h1>
        <p>No hidden fees. No surprises. Upgrade or cancel anytime.</p>
        <div className="billing-toggle">
          <span className={"toggle-label" + (yearly ? "" : " active")}>Monthly</span>
          <label className="toggle-switch">
            <input type="checkbox" checked={yearly} onChange={() => setYearly((p) => !p)} />
            <span className="toggle-slider"></span>
          </label>
          <span className={"toggle-label" + (yearly ? " active" : "")}>Yearly <span className="toggle-badge">Save 20%</span></span>
        </div>
      </header>
      <section id="pricing" className="pricing-grid">
        {plans.map((p, i) => <PricingCard plan={p} yearly={yearly} key={i} />)}
      </section>
      <FAQ />
      <footer className="footer">
        <p>&copy; 2026 SaaSify. All rights reserved.</p>
      </footer>
    </>
  );
}

const root = createRoot(document.getElementById("root"));
root.render(<App />);
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
    "portfolio": {
        "name": "Portfolio",
        "description": "Clean portfolio with project cards, about section, stats, and contact area — for designers and developers.",
        "frameworks": ["vanilla", "react"],
        "preview_snippet": "<h1>Portfolio</h1><p>Projects + about + contact</p>",
        "files": {
            "vanilla": [
                ("index.html", _PORTFOLIO_HTML, "html"),
                ("style.css", _PORTFOLIO_CSS, "css"),
                ("script.js", _LANDING_JS, "javascript"),
            ],
            "react": [
                ("App.jsx", _PORTFOLIO_REACT_APP, "jsx"),
                ("style.css", _PORTFOLIO_CSS, "css"),
            ],
        },
    },
    "blog": {
        "name": "Blog",
        "description": "Serif-style blog layout with article cards, categories, newsletter signup, and responsive design.",
        "frameworks": ["vanilla", "react"],
        "preview_snippet": "<h1>Blog</h1><p>Articles + newsletter + footer</p>",
        "files": {
            "vanilla": [
                ("index.html", _BLOG_HTML, "html"),
                ("style.css", _BLOG_CSS, "css"),
                ("script.js", _BLOG_JS, "javascript"),
            ],
            "react": [
                ("App.jsx", _BLOG_REACT_APP, "jsx"),
                ("style.css", _BLOG_CSS, "css"),
            ],
        },
    },
    "pricing": {
        "name": "Pricing",
        "description": "Three-tier pricing page with monthly/yearly toggle, feature lists, FAQ accordion, and call-to-action.",
        "frameworks": ["vanilla", "react"],
        "preview_snippet": "<h1>Pricing</h1><p>3 plans + FAQ + CTA</p>",
        "files": {
            "vanilla": [
                ("index.html", _PRICING_HTML, "html"),
                ("style.css", _PRICING_CSS, "css"),
                ("script.js", _PRICING_JS, "javascript"),
            ],
            "react": [
                ("App.jsx", _PRICING_REACT_APP, "jsx"),
                ("style.css", _PRICING_CSS, "css"),
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
