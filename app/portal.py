"""Interactive Web Portal for Customer Management System - Story S1-05."""

def get_portal_html() -> str:
    return """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>H??? th???ng Qu???n l?? Kh??ch h??ng - Story S1-05 Ph??n quy???n & Ph???m vi d??? li???u</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: rgba(22, 30, 49, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --primary: #4f46e5;
      --primary-hover: #4338ca;
      --primary-light: rgba(99, 102, 241, 0.15);
      --accent: #06b6d4;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.5;
      background-image: 
        radial-gradient(at 0% 0%, rgba(79, 70, 229, 0.18) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(6, 182, 212, 0.12) 0px, transparent 50%);
      background-attachment: fixed;
    }

    header {
      border-bottom: 1px solid var(--card-border);
      background: rgba(11, 15, 25, 0.8);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .header-inner {
      max-width: 1280px;
      margin: 0 auto;
      padding: 16px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-logo {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, var(--primary), var(--accent));
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 18px;
      color: white;
      box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
    }
    .brand-title {
      font-size: 16px;
      font-weight: 700;
      color: #fff;
    }
    .brand-sub {
      font-size: 12px;
      color: var(--text-muted);
    }

    .nav-actions {
      display: flex;
      gap: 12px;
    }
    .btn {
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid transparent;
      font-family: inherit;
    }
    .btn-primary {
      background: var(--primary);
      color: white;
    }
    .btn-primary:hover {
      background: var(--primary-hover);
      box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4);
    }
    .btn-outline {
      background: rgba(255, 255, 255, 0.05);
      border-color: var(--card-border);
      color: var(--text);
    }
    .btn-outline:hover {
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.2);
    }
    .btn-danger {
      background: rgba(239, 68, 68, 0.15);
      border-color: rgba(239, 68, 68, 0.3);
      color: #fca5a5;
    }
    .btn-danger:hover {
      background: rgba(239, 68, 68, 0.25);
    }

    .container {
      max-width: 1280px;
      margin: 0 auto;
      padding: 32px 24px;
    }

    .hero-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      border-radius: 9999px;
      background: var(--primary-light);
      border: 1px solid rgba(99, 102, 241, 0.3);
      color: #a5b4fc;
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 12px;
    }
    .hero h1 {
      font-size: 28px;
      font-weight: 800;
      margin-bottom: 8px;
      background: linear-gradient(135deg, #ffffff 60%, #94a3b8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .hero p {
      color: var(--text-muted);
      font-size: 14px;
      max-width: 800px;
    }

    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
      margin-top: 28px;
    }
    @media (max-width: 900px) {
      .grid-2 { grid-template-columns: 1fr; }
    }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 24px;
      backdrop-filter: blur(16px);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
    }
    .card-title {
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    /* Table feature requirements */
    .feature-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    .feature-table th {
      text-align: left;
      padding: 10px 12px;
      color: var(--text-muted);
      border-bottom: 1px solid var(--card-border);
      font-weight: 600;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }
    .feature-table td {
      padding: 12px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }
    .feature-table tr:last-child td { border-bottom: none; }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-primary { background: rgba(99, 102, 241, 0.2); color: #a5b4fc; }
    .badge-success { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
    .badge-warning { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
    .badge-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }

    /* Interactive section */
    .user-picker {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-bottom: 16px;
    }
    @media (max-width: 640px) {
      .user-picker { grid-template-columns: 1fr 1fr; }
    }
    .user-btn {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 12px;
      cursor: pointer;
      text-align: left;
      transition: all 0.2s ease;
      color: var(--text);
    }
    .user-btn:hover {
      background: rgba(255, 255, 255, 0.07);
      border-color: rgba(99, 102, 241, 0.4);
    }
    .user-btn.active {
      background: rgba(79, 70, 229, 0.15);
      border-color: var(--primary);
      box-shadow: 0 0 0 1px var(--primary);
    }
    .user-btn-name { font-size: 13px; font-weight: 700; }
    .user-btn-role { font-size: 11px; margin-top: 2px; }

    .current-user-card {
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 14px 16px;
      margin-bottom: 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .user-info { display: flex; align-items: center; gap: 12px; }
    .avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, #6366f1, #06b6d4);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 14px;
    }

    .scope-selector {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }
    .scope-btn {
      padding: 6px 14px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
      transition: all 0.2s;
    }
    .scope-btn:hover { background: rgba(255, 255, 255, 0.1); color: #fff; }
    .scope-btn.active {
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
    }

    .action-group {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 16px;
    }

    .console-box {
      background: #050811;
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 14px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      max-height: 280px;
      overflow-y: auto;
    }
    .status-line {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .customer-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      font-size: 12px;
    }
    .customer-table th, .customer-table td {
      padding: 8px 10px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      text-align: left;
    }
    .customer-table th { background: rgba(255, 255, 255, 0.03); color: var(--text-muted); }

    footer {
      border-top: 1px solid var(--card-border);
      padding: 24px;
      text-align: center;
      color: var(--text-muted);
      font-size: 12px;
      margin-top: 40px;
    }
  </style>
</head>
<body>

  <header>
    <div class="header-inner">
      <div class="brand">
        <div class="brand-logo">K5</div>
        <div>
          <div class="brand-title">H??? th???ng Qu???n l?? Kh??ch h??ng</div>
          <div class="brand-sub">K4S5 Nh??m 5 &bull; Backend FastAPI</div>
        </div>
      </div>
      <div class="nav-actions">
        <a href="/docs" target="_blank" class="btn btn-primary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
          M??? Swagger UI (/docs)
        </a>
        <a href="/redoc" target="_blank" class="btn btn-outline">ReDoc</a>
      </div>
    </div>
  </header>

  <main class="container">
    <div class="hero">
      <div class="hero-badge">Story S1-05 &bull; Ph??n quy???n + Ph???m vi d??? li???u (Backend)</div>
      <h1>C???ng Ki???m Th??? Quy???n & D??? Li???u</h1>
      <p>C?? ch??? x??c th???c JWT, ph??n quy???n Role (ADMIN, MANAGER, USER) v?? ki???m so??t ph???m vi truy c???p d??? li???u (MY, TEAM, ALL) theo ti??u chu???n b???o m???t API c???a FastAPI.</p>
    </div>

    <div class="grid-2">
      <!-- C???t tr??i: B???ng ?????c t??? ch???c n??ng S1-05 -->
      <div class="card">
        <div class="card-title">
          <span>????</span> ?????c T??? Ch???c N??ng Story S1-05
        </div>
        <table class="feature-table">
          <thead>
            <tr>
              <th>Ch???c n??ng</th>
              <th>?? ngh??a & H??nh vi</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>???? JWT Authentication</strong></td>
              <td>Ki???m tra ng?????i d??ng ???? ????ng nh???p ch??a qua Bearer Token</td>
            </tr>
            <tr>
              <td><strong>???? Role</strong></td>
              <td>
                Ph??n bi???t 3 quy???n:
                <span class="badge badge-primary">ADMIN</span>
                <span class="badge badge-warning">MANAGER</span>
                <span class="badge badge-success">USER</span>
              </td>
            </tr>
            <tr>
              <td><strong>???? Authorization</strong></td>
              <td>Ng?????i d??ng kh??ng ????? quy???n truy c???p API &rarr; <span class="badge badge-danger">403 Forbidden</span></td>
            </tr>
            <tr>
              <td><strong>???? Authentication</strong></td>
              <td>Thi???u token ho???c token sai / h???t h???n &rarr; <span class="badge badge-danger">401 Unauthorized</span></td>
            </tr>
            <tr>
              <td><strong>??????? MY Scope</strong></td>
              <td>Ch??? xem v?? thao t??c d??? li???u do ch??nh user s??? h???u (<code style="color:#a5b4fc">owner_id</code>)</td>
            </tr>
            <tr>
              <td><strong>???? TEAM Scope</strong></td>
              <td>Xem v?? thao t??c d??? li???u thu???c c??ng nh??m v???i user (<code style="color:#6ee7b7">team_id</code>)</td>
            </tr>
            <tr>
              <td><strong>???? ALL Scope</strong></td>
              <td>Ch??? ADMIN ???????c quy???n xem v?? qu???n tr??? to??n b??? d??? li???u</td>
            </tr>
            <tr>
              <td><strong>??????? Record-level</strong></td>
              <td>Ki???m tra quy???n truy c???p tr??n t???ng kh??ch h??ng khi xem/s???a</td>
            </tr>
            <tr>
              <td><strong>???? Automated Test</strong></td>
              <td><span class="badge badge-success">25/25 Tests Passed</span> (Pytest)</td>
            </tr>
            <tr>
              <td><strong>???? Git Branch</strong></td>
              <td><code style="color:#06b6d4; font-size:11px;">feature/S1-05-permission-backend</code></td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- C???t ph???i: Live Interactive Demo -->
      <div class="card">
        <div class="card-title">
          <span>???</span> Tr???i Nghi???m & Ki???m Th??? Quy???n Tr???c Ti???p
        </div>

        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 10px;">1. Ch???n t??i kho???n ????? ????ng nh???p:</p>
        <div class="user-picker">
          <div class="user-btn active" onclick="switchUser('admin@gmail.com')">
            <div class="user-btn-name">Admin</div>
            <div class="user-btn-role" style="color:#a5b4fc;">ADMIN &bull; All</div>
          </div>
          <div class="user-btn" onclick="switchUser('manager@gmail.com')">
            <div class="user-btn-name">Manager A</div>
            <div class="user-btn-role" style="color:#fcd34d;">MGR &bull; Team 1</div>
          </div>
          <div class="user-btn" onclick="switchUser('user1@gmail.com')">
            <div class="user-btn-name">User 1</div>
            <div class="user-btn-role" style="color:#6ee7b7;">USER &bull; Team 1</div>
          </div>
          <div class="user-btn" onclick="switchUser('user2@gmail.com')">
            <div class="user-btn-name">User 2</div>
            <div class="user-btn-role" style="color:#6ee7b7;">USER &bull; Team 2</div>
          </div>
        </div>

        <div class="current-user-card" id="userInfoBox">
          <div class="user-info">
            <div class="avatar" id="userAvatar">A</div>
            <div>
              <div style="font-weight: 700; font-size: 13px;" id="userName">Admin</div>
              <div style="font-size: 11px; color: var(--text-muted);" id="userEmail">admin@gmail.com</div>
            </div>
          </div>
          <div>
            <span class="badge badge-primary" id="userRoleBadge">ROLE: ADMIN</span>
            <span class="badge badge-success" id="userTeamBadge">TEAM: ALL</span>
          </div>
        </div>

        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">2. Ch???n ph???m vi d??? li???u (Scope) ????? l???c:</p>
        <div class="scope-selector">
          <button class="scope-btn" id="scopeBtnDefault" onclick="setScope('')">M???c ?????nh (Theo Role)</button>
          <button class="scope-btn active" id="scopeBtnMY" onclick="setScope('MY')">MY</button>
          <button class="scope-btn" id="scopeBtnTEAM" onclick="setScope('TEAM')">TEAM</button>
          <button class="scope-btn" id="scopeBtnALL" onclick="setScope('ALL')">ALL</button>
        </div>

        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">3. Thao t??c ki???m tra quy???n:</p>
        <div class="action-group">
          <button class="btn btn-primary" onclick="fetchCustomers()">
            <span>????</span> L???y Kh??ch H??ng (GET /customers)
          </button>
          <button class="btn btn-outline" onclick="fetchUsers()">
            <span>????</span> Qu???n l?? Users (GET /users)
          </button>
          <button class="btn btn-outline" onclick="createDemoCustomer()">
            <span>???</span> Th??m KH (POST)
          </button>
          <button class="btn btn-danger" onclick="deleteDemoCustomer()">
            <span>???????</span> X??a KH (DELETE)
          </button>
        </div>

        <div class="console-box" id="consoleOutput">
          <div class="status-line">
            <span style="color:#10b981;">??? S???n s??ng:</span> ??ang ch??? l???nh th??? nghi???m...
          </div>
          <div style="color: #6b7280; font-size: 11px;">B???m n??t thao t??c b??n tr??n ????? g???i request c?? k??m token JWT ?????n backend.</div>
        </div>
      </div>
    </div>
  </main>

  <footer>
    H??? th???ng Qu???n l?? Kh??ch h??ng &bull; Nh??m 5 K4S5 &bull; Nh??nh git: <code>feature/S1-05-permission-backend</code> &bull; FastAPI + Python
  </footer>

  <script>
    let currentToken = '';
    let currentEmail = 'admin@gmail.com';
    let currentScope = '';

    const users = {
      'admin@gmail.com': { name: 'Admin', role: 'ADMIN', team: 'ALL', defaultScope: 'ALL' },
      'manager@gmail.com': { name: 'Manager Team A', role: 'MANAGER', team: 'Team 1', defaultScope: 'TEAM' },
      'user1@gmail.com': { name: 'User 1', role: 'USER', team: 'Team 1', defaultScope: 'MY' },
      'user2@gmail.com': { name: 'User 2', role: 'USER', team: 'Team 2', defaultScope: 'MY' }
    };

    async function login(email) {
      currentEmail = email;
      try {
        const res = await fetch('/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email, password: '123456' })
        });
        const data = await res.json();
        if (res.ok) {
          currentToken = data.access_token;
          const u = users[email];
          document.getElementById('userName').textContent = data.user.full_name;
          document.getElementById('userEmail').textContent = data.user.email;
          document.getElementById('userAvatar').textContent = data.user.full_name.charAt(0);
          document.getElementById('userRoleBadge').textContent = 'ROLE: ' + data.user.role;
          document.getElementById('userTeamBadge').textContent = 'TEAM: ' + (u.team || 'None');
          
          logConsole(200, '????ng nh???p th??nh c??ng v???i ' + email + ' (Role: ' + data.user.role + ')', {
            access_token: data.access_token.substring(0, 32) + '...',
            user: data.user
          });
        } else {
          logConsole(res.status, 'L???i ????ng nh???p', data);
        }
      } catch (err) {
        logConsole(500, 'L???i k???t n???i', { error: err.message });
      }
    }

    function switchUser(email) {
      document.querySelectorAll('.user-btn').forEach(btn => btn.classList.remove('active'));
      event.currentTarget.classList.add('active');
      login(email);
    }

    function setScope(scope) {
      currentScope = scope;
      document.querySelectorAll('.scope-btn').forEach(btn => btn.classList.remove('active'));
      if (!scope) document.getElementById('scopeBtnDefault').classList.add('active');
      if (scope === 'MY') document.getElementById('scopeBtnMY').classList.add('active');
      if (scope === 'TEAM') document.getElementById('scopeBtnTEAM').classList.add('active');
      if (scope === 'ALL') document.getElementById('scopeBtnALL').classList.add('active');
    }

    async function fetchCustomers() {
      const url = currentScope ? `/customers?scope=${currentScope}` : '/customers';
      try {
        const res = await fetch(url, {
          headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        const data = await res.json();
        logConsole(res.status, `GET ${url}`, data, 'customers');
      } catch (err) {
        logConsole(500, `GET ${url} Th???t b???i`, { error: err.message });
      }
    }

    async function fetchUsers() {
      try {
        const res = await fetch('/users', {
          headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        const data = await res.json();
        logConsole(res.status, 'GET /users (ADMIN Only)', data);
      } catch (err) {
        logConsole(500, 'GET /users Th???t b???i', { error: err.message });
      }
    }

    async function createDemoCustomer() {
      try {
        const res = await fetch('/customers', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${currentToken}`
          },
          body: JSON.stringify({
            name: 'Kh??ch h??ng th??? nghi???m l??c ' + new Date().toLocaleTimeString(),
            phone: '0987654321',
            company: 'C??ng ty Test'
          })
        });
        const data = await res.json();
        logConsole(res.status, 'POST /customers (ADMIN & MANAGER only)', data);
      } catch (err) {
        logConsole(500, 'POST /customers Th???t b???i', { error: err.message });
      }
    }

    async function deleteDemoCustomer() {
      try {
        const res = await fetch('/customers/1', {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        const data = await res.json();
        logConsole(res.status, 'DELETE /customers/1 (ADMIN only)', data);
      } catch (err) {
        logConsole(500, 'DELETE /customers/1 Th???t b???i', { error: err.message });
      }
    }

    function logConsole(status, title, body, mode) {
      const isSuccess = status >= 200 && status < 300;
      const statusColor = isSuccess ? '#10b981' : (status === 403 ? '#f59e0b' : '#ef4444');
      
      let html = `
        <div class="status-line">
          <span style="background:${statusColor}22; color:${statusColor}; padding:2px 6px; border-radius:4px; font-weight:700;">HTTP ${status}</span>
          <span style="font-weight:600; color:#fff;">${title}</span>
        </div>
      `;

      if (mode === 'customers' && body.customers && body.customers.length > 0) {
        html += `
          <div style="color:#a5b4fc; font-size:11px; margin-bottom:4px;">Ph???m vi: <b>${body.scope}</b> &bull; T???ng: <b>${body.total} kh??ch h??ng</b></div>
          <table class="customer-table">
            <thead>
              <tr><th>ID</th><th>T??n</th><th>Owner ID</th><th>Team ID</th><th>C??ng ty</th></tr>
            </thead>
            <tbody>
              ${body.customers.map(c => `
                <tr>
                  <td>#${c.id}</td>
                  <td style="color:#fff; font-weight:600;">${c.name}</td>
                  <td>User ${c.owner_id}</td>
                  <td>Team ${c.team_id || '-'}</td>
                  <td>${c.company || '-'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      } else {
        html += `<pre style="color:${isSuccess ? '#94a3b8' : '#fca5a5'}; white-space:pre-wrap; word-break:break-all;">${JSON.stringify(body, null, 2)}</pre>`;
      }

      document.getElementById('consoleOutput').innerHTML = html;
    }

    // Auto-login as Admin initially
    window.addEventListener('DOMContentLoaded', () => {
      login('admin@gmail.com');
    });
  </script>
</body>
</html>
"""
