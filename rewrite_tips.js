const fs = require('fs');
const file = 'c:/Users/BAB AL SAFA/Desktop/Smart Hotel ERP/hotel-frontend/src/pages/CashierDashboard.js';
let content = fs.readFileSync(file, 'utf8');

const tipsStartIdx = content.indexOf("{activeTab === 'tips' && (");
const endAnimatePresenceIdx = content.indexOf("</AnimatePresence>", tipsStartIdx);

const oldTipsBlock = content.slice(tipsStartIdx, endAnimatePresenceIdx);

const newTipsBlock = `{activeTab === 'tips' && (
            <motion.div key="tips" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div style={styles.sectionHeaderRow}>
                <div>
                  <div style={styles.sectionKicker}>ANALYTICS</div>
                  <h1 style={styles.sectionTitle}>Tips History</h1>
                </div>
              </div>
              <div style={{ ...styles.metricGrid, marginTop: '20px' }}>
                  <MetricCard icon={<CreditCard size={24}/>} label="Total Tips Collected" value={\`\${settings?.currency_symbol || 'ETB'} \${(stats?.completedTips || 0).toFixed(2)}\`} tone="amber" />
              </div>
              <div style={{ ...styles.panel, marginTop: '30px' }}>
                <div style={styles.panelHeader}>
                  <h3 style={styles.panelTitle}>Completed Orders with Tips</h3>
                </div>
                {completedBills.filter(o => parseFloat(o.tip_amount || 0) > 0).length > 0 ? (
                  <div style={styles.orderList}>
                      {completedBills.filter(o => parseFloat(o.tip_amount || 0) > 0).map(order => (
                        <div key={order.id} style={styles.orderCard}>
                          <div style={styles.orderCardTop}>
                            <strong style={styles.orderId}>ORD-{order.id}</strong>
                            <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#10b981', background: '#dcfce7', padding: '4px 8px', borderRadius: '40px' }}>
                               Tip: {settings?.currency_symbol || 'ETB'} {Number(order.tip_amount).toFixed(2)}
                            </span>
                          </div>
                          <div style={styles.orderStatsLine}>
                            <span>Table {order.table_code}</span> • <span>{order.waiter_name}</span>
                          </div>
                        </div>
                      ))}
                  </div>
                ) : (
                  <div style={styles.emptyState}>No tips collected yet.</div>
                )}
              </div>
            </motion.div>
          )}
        `;

content = content.replace(oldTipsBlock, newTipsBlock);
fs.writeFileSync(file, content);
console.log('Tips block updated!');
