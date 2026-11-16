import os

def update_app_js():
    path = 'hotel-frontend/src/App.js'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add tab guard in DashboardLayout
    target1 = """    if (isInvTab && hotelSettings.module_inventory === false) setActiveTab('dashboard');
    if (isFinTab && hotelSettings.module_finance === false) setActiveTab('dashboard');
  }, [hotelSettings, activeTab, setActiveTab]);"""

    repl1 = """    if (isInvTab && hotelSettings.module_inventory === false) setActiveTab('dashboard');
    if (isFinTab && hotelSettings.module_finance === false) setActiveTab('dashboard');
  }, [hotelSettings, activeTab, setActiveTab]);

  useEffect(() => {
    const role = (userData?.role || '').toLowerCase().trim();
    if (role === 'hotel_manager' && (activeTab === 'users' || activeTab === 'settings')) {
      setActiveTab('dashboard');
    }
    if (role === 'inventory') {
      const isInvAllowed = ['inventory', 'stocktaking', 'procurement', 'report_inventory'].includes(activeTab) || activeTab.startsWith('procurement_');
      if (!isInvAllowed) {
        setActiveTab('inventory');
      }
    }
  }, [userData?.role, activeTab, setActiveTab]);"""

    assert target1 in content, "target1 not found"
    content = content.replace(target1, repl1, 1)

    # 2. Page title
    target2 = """            {activeTab === 'dashboard' && (
              <motion.div key="dash" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                <h1 style={pageTitle}>Admin Dashboard Overview</h1>
                <DashboardContent hotelSettings={hotelSettings} />
              </motion.div>
            )}"""

    repl2 = """            {activeTab === 'dashboard' && (
              <motion.div key="dash" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                <h1 style={pageTitle}>
                  {userData?.role?.toLowerCase().trim() === 'hotel_manager'
                    ? 'Hotel Operations Overview'
                    : 'Admin Dashboard Overview'}
                </h1>
                <DashboardContent hotelSettings={hotelSettings} />
              </motion.div>
            )}"""

    assert target2 in content, "target2 not found"
    content = content.replace(target2, repl2, 1)

    # 3. Guard users and settings
    target3 = """            {activeTab === 'users'     && <UserManager />}
            {activeTab === 'settings'  && <SystemSettingsManager />}"""

    repl3 = """            {activeTab === 'users'     && !['hotel_manager', 'inventory'].includes((userData?.role || '').toLowerCase().trim()) && <UserManager />}
            {activeTab === 'settings'  && !['hotel_manager', 'inventory'].includes((userData?.role || '').toLowerCase().trim()) && <SystemSettingsManager />}"""

    assert target3 in content, "target3 not found"
    content = content.replace(target3, repl3, 1)

    # 4. Tab defaults on load and login
    target4 = """      if (parsed.role?.toLowerCase().trim() === 'finance') setActiveTab('finance');
    }
  }, []);

  const handleLoginSuccess = (user) => {
    setUserData(user);
    const role = user.role?.toLowerCase().trim();
    if (role === 'finance') {
      setActiveTab('finance');
    } else {
      setActiveTab('dashboard');
    }
  };"""

    repl4 = """      const r = parsed.role?.toLowerCase().trim();
      if (r === 'finance') setActiveTab('finance');
      else if (r === 'inventory') setActiveTab('inventory');
    }
  }, []);

  const handleLoginSuccess = (user) => {
    setUserData(user);
    const role = user.role?.toLowerCase().trim();
    if (role === 'finance') {
      setActiveTab('finance');
    } else if (role === 'inventory') {
      setActiveTab('inventory');
    } else {
      setActiveTab('dashboard');
    }
  };"""

    assert target4 in content, "target4 not found"
    content = content.replace(target4, repl4, 1)

    # 5. renderDashboard routing
    target5 = """    switch (role) {
      case 'admin':
      case 'finance':
        return <DashboardLayout activeTab={activeTab} setActiveTab={setActiveTab} userData={user} handleLogout={handleLogout} />;
      case 'waiter':
        return <WaiterDashboard userData={user} handleLogout={handleLogout} />;
      case 'cashier':
        return <CashierDashboard userData={user} handleLogout={handleLogout} />;
      case 'kitchen':
        return <KitchenDashboard userData={user} handleLogout={handleLogout} />;
      case 'bar':
        return <BarDashboard userData={user} handleLogout={handleLogout} />;
      case 'reception':
        return <ReceptionDashboard userData={user} handleLogout={handleLogout} />;
      case 'inventory':
        return <InventoryDashboard userData={user} handleLogout={handleLogout} />;
      case 'customer':"""

    repl5 = """    switch (role) {
      case 'admin':
      case 'finance':
      case 'hotel_manager':
        return <DashboardLayout activeTab={activeTab} setActiveTab={setActiveTab} userData={user} handleLogout={handleLogout} />;
      case 'inventory':
        return <DashboardLayout activeTab={activeTab || 'inventory'} setActiveTab={setActiveTab} userData={user} handleLogout={handleLogout} />;
      case 'waiter':
        return <WaiterDashboard userData={user} handleLogout={handleLogout} />;
      case 'cashier':
        return <CashierDashboard userData={user} handleLogout={handleLogout} />;
      case 'kitchen':
        return <KitchenDashboard userData={user} handleLogout={handleLogout} />;
      case 'bar':
        return <BarDashboard userData={user} handleLogout={handleLogout} />;
      case 'reception':
        return <ReceptionDashboard userData={user} handleLogout={handleLogout} />;
      case 'customer':"""

    assert target5 in content, "target5 not found"
    content = content.replace(target5, repl5, 1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("App.js updated successfully.")


def update_sidebar_js():
    path = 'hotel-frontend/src/Sidebar.js'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update isChildVisible
    target_child = """  const isChildVisible = (child) => {
    if (['report_police', 'report_occupancy', 'report_bookings'].includes(child.id)) {
      if (hotelSettings?.module_rooms === false) return false;
    }"""

    repl_child = """  const isChildVisible = (child) => {
    if (userRole === 'inventory') {
      if (child.id !== 'report_inventory' && !child.id.startsWith('procurement_')) {
        return false;
      }
    }
    if (['report_police', 'report_occupancy', 'report_bookings'].includes(child.id)) {
      if (hotelSettings?.module_rooms === false) return false;
    }"""

    assert target_child in content, "target_child not found"
    content = content.replace(target_child, repl_child, 1)

    # 2. Update isItemVisible
    target_item = """    if (userRole === 'finance' && !['dashboard', 'finance', 'inventory', 'procurement', 'all_reports'].includes(item.id)) return false;
    return true;
  };"""

    repl_item = """    if (userRole === 'finance' && !['dashboard', 'finance', 'inventory', 'procurement', 'all_reports'].includes(item.id)) return false;
    if (userRole === 'hotel_manager' && ['users', 'settings'].includes(item.id)) return false;
    if (userRole === 'inventory' && !['inventory', 'stocktaking', 'procurement', 'all_reports'].includes(item.id)) return false;
    return true;
  };"""

    assert target_item in content, "target_item not found"
    content = content.replace(target_item, repl_item, 1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Sidebar.js updated successfully.")


def update_user_manager_jsx():
    path = 'hotel-frontend/src/UserManager.jsx'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. getAvailableRoles
    target_roles = """  const getAvailableRoles = () => {
    let available = ['Admin'];"""

    repl_roles = """  const getAvailableRoles = () => {
    let available = ['Admin', 'Hotel Manager'];"""

    assert target_roles in content, "target_roles not found"
    content = content.replace(target_roles, repl_roles, 1)

    # 2. handleEdit role population
    target_edit = """      email: user.email || '',
      role: user.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : 'Waiter',"""

    repl_edit = """      email: user.email || '',
      role: user.role
        ? (user.role.toLowerCase() === 'hotel_manager' ? 'Hotel Manager' : user.role.charAt(0).toUpperCase() + user.role.slice(1))
        : 'Waiter',"""

    assert target_edit in content, "target_edit not found"
    content = content.replace(target_edit, repl_edit, 1)

    # 3. handleSubmit normalized role
    target_submit = """    data.append('email', email);
    data.append('role', formData.role.toLowerCase());
    data.append('phone_number', formData.phone_number);"""

    repl_submit = """    data.append('email', email);
    const normalizedRole = formData.role.toLowerCase().trim() === 'hotel manager'
      ? 'hotel_manager'
      : formData.role.toLowerCase().trim();
    data.append('role', normalizedRole);
    data.append('phone_number', formData.phone_number);"""

    assert target_submit in content, "target_submit not found"
    content = content.replace(target_submit, repl_submit, 1)

    # 4. getFilteredUsers
    target_filter = """      const roleMatch = roleFilter === 'All Roles' || (user.role && user.role.toLowerCase() === roleFilter.toLowerCase());"""

    repl_filter = """      const roleMatch = roleFilter === 'All Roles' ||
        (user.role && (
          user.role.toLowerCase() === roleFilter.toLowerCase() ||
          (roleFilter === 'Hotel Manager' && user.role.toLowerCase() === 'hotel_manager')
        ));"""

    assert target_filter in content, "target_filter not found"
    content = content.replace(target_filter, repl_filter, 1)

    # 5. Table cell display
    target_table = """                <td style={tdStyle}><span style={getRoleBadgeStyle(user.role)}>{user.role}</span></td>"""

    repl_table = """                <td style={tdStyle}><span style={getRoleBadgeStyle(user.role)}>{user.role === 'hotel_manager' ? 'Hotel Manager' : user.role}</span></td>"""

    assert target_table in content, "target_table not found"
    content = content.replace(target_table, repl_table, 1)

    # 6. getRoleBadgeStyle
    target_badge = """  switch (role?.toLowerCase()) {
    case 'admin': return { ...base, backgroundColor: '#f1f5f9', color: '#64748b' };
    case 'waiter': return { ...base, backgroundColor: '#fef3c7', color: '#b45309' };"""

    repl_badge = """  switch (role?.toLowerCase()) {
    case 'admin': return { ...base, backgroundColor: '#fee2e2', color: '#b91c1c' };
    case 'hotel_manager': return { ...base, backgroundColor: '#ede9fe', color: '#6d28d9' };
    case 'inventory': return { ...base, backgroundColor: '#fef9c3', color: '#854d0e' };
    case 'waiter': return { ...base, backgroundColor: '#fef3c7', color: '#b45309' };"""

    assert target_badge in content, "target_badge not found"
    content = content.replace(target_badge, repl_badge, 1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("UserManager.jsx updated successfully.")

if __name__ == '__main__':
    update_app_js()
    update_sidebar_js()
    update_user_manager_jsx()
