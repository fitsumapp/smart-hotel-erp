const fs = require('fs');
const file = 'c:/Users/BAB AL SAFA/Desktop/Smart Hotel ERP/hotel-frontend/src/pages/CashierDashboard.js';
let content = fs.readFileSync(file, 'utf8');

const startIdx = content.indexOf("{activeTab === 'orders' && (");
const tipsStartIdx = content.indexOf("{activeTab === 'tips' && (");

if (startIdx === -1 || tipsStartIdx === -1) {
  console.error("Could not find boundaries");
  process.exit(1);
}

const oldOrdersBlock = content.slice(startIdx, tipsStartIdx);

const newOrdersBlock = `{activeTab === 'orders' && (
            <motion.div key="orders" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', height: '100%', gap: '20px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div style={styles.sectionHeaderRow}>
                    <div>
                      <div style={styles.sectionKicker}>TRANSACTIONS</div>
                      <h1 style={styles.sectionTitle}>Billing & Checkout</h1>
                    </div>
                    <div style={styles.searchBox}>
                      <Search size={18} color="#94a3b8" />
                      <input type="text" placeholder="Search table or order ID..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} style={styles.searchInput} />
                    </div>
                  </div>

                  <div style={{ ...styles.panel, flex: 1, overflowY: 'auto' }}>
                    <div style={styles.panelHeader}><h3 style={styles.panelTitle}>Pending Bills</h3></div>
                    {filteredOrders.length > 0 ? (
                      <div style={styles.orderList}>
                        {filteredOrders.map(bill => (
                          <div key={bill.id} onClick={() => setSelectedOrder(bill)}
                            style={{ ...styles.orderCard, borderLeft: selectedOrder?.id === bill.id ? '4px solid #10b981' : 'none', background: selectedOrder?.id === bill.id ? '#f0fdf4' : '#fff', cursor: 'pointer' }}>
                            <div style={styles.orderCardTop}>
                              <strong style={styles.orderId}>ORD-{bill.id}</strong>
                              <span style={styles.pricePill}>{settings?.currency_symbol || 'ETB'} {bill.total_amount}</span>
                            </div>
                            <div style={styles.orderStatsLine}>
                              <span>Table {bill.table_code}</span> • <span>{bill.waiter_name}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={styles.emptyState}>No pending bills.</div>
                    )}
                    
                    <div style={{ ...styles.panelHeader, marginTop: '20px' }}><h3 style={styles.panelTitle}>Completed Bills</h3></div>
                    {filteredCompletedOrders.length > 0 ? (
                      <div style={styles.orderList}>
                        {filteredCompletedOrders.map(bill => (
                          <div key={bill.id} onClick={() => setSelectedOrder(bill)}
                            style={{ ...styles.orderCard, borderLeft: selectedOrder?.id === bill.id ? '4px solid #3b82f6' : 'none', background: selectedOrder?.id === bill.id ? '#eff6ff' : '#fff', cursor: 'pointer' }}>
                            <div style={styles.orderCardTop}>
                              <strong style={styles.orderId}>ORD-{bill.id}</strong>
                              <span style={styles.pricePill}>{settings?.currency_symbol || 'ETB'} {bill.total_amount}</span>
                            </div>
                            <div style={styles.orderStatsLine}>
                              <span>Table {bill.table_code}</span> • <span>Completed</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={styles.emptyState}>No completed bills.</div>
                    )}
                  </div>
                </div>

                <div style={styles.cartPanel}>
                  {selectedOrder ? (
                    <motion.div initial={{ x: 20 }} animate={{ x: 0 }}>
                      <div style={styles.cartHeader}>
                        <div>
                          <div style={{ fontSize: '13px', color: '#64748b', fontWeight: '600' }}>Table Checkout</div>
                          <div style={{ fontSize: '20px', fontWeight: '800', color: '#0f172a' }}>{selectedOrder.table_code}</div>
                        </div>
                        <button onClick={() => setSelectedOrder(null)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}><X size={20} color="#94a3b8"/></button>
                      </div>
                      <div style={styles.cartItems}>
                         {selectedOrder.items?.map((item, i) => (
                           <div key={i} style={styles.cartItemRow}>
                              <div style={styles.cartItemInfo}>
                                <div style={styles.cartItemName}>{item.menu_item_name}</div>
                                <div style={styles.cartItemPrice}>{settings?.currency_symbol || 'ETB'} {item.price_at_order}</div>
                              </div>
                              <div style={{ fontSize: '12px', fontWeight: 'bold' }}>x{item.quantity}</div>
                              <div style={styles.cartItemTotal}>{(item.quantity * item.price_at_order).toFixed(2)}</div>
                           </div>
                         ))}
                      </div>
                      <div style={styles.cartSummary}>
                        <div style={styles.summaryRow}><span>Sub-Total</span><span>{settings?.currency_symbol || 'ETB'} {(isCompletedOrder ? Number(selectedOrder.sub_total || 0) : billSummary.subTotal).toFixed(2)}</span></div>
                        <div style={styles.summaryRow}><span>Service ({serviceRate}%)</span><span>{settings?.currency_symbol || 'ETB'} {(isCompletedOrder ? Number(selectedOrder.service_charge_amount || 0) : billSummary.serviceCharge).toFixed(2)}</span></div>
                        <div style={styles.summaryRow}><span>VAT ({vatRate}%)</span><span>{settings?.currency_symbol || 'ETB'} {(isCompletedOrder ? Number(selectedOrder.vat_amount || 0) : billSummary.vat).toFixed(2)}</span></div>
                        {isCompletedOrder && <div style={styles.summaryRow}><span>Tip Amount</span><span style={{color: '#10b981', fontWeight: 'bold'}}>{settings?.currency_symbol || 'ETB'} {Number(selectedOrder.tip_amount || 0).toFixed(2)}</span></div>}
                        <div style={styles.grandTotalRow}><span>Grand Total</span><span>{settings?.currency_symbol || 'ETB'} {(isCompletedOrder ? Number(selectedOrder.total_amount || 0) : billSummary.grandTotal).toFixed(2)}</span></div>
                      </div>
                      
                      {!isCompletedOrder ? (
                        <>
                          <div style={{ padding: '0 20px 20px 20px' }}>
                            <p style={{ fontSize: '12px', fontWeight: 'bold', marginBottom: '8px', color: '#1e293b' }}>Payment Method:</p>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '10px' }}>
                              {['Cash', 'Telebirr', 'Card'].map(m => (
                                <button key={m} onClick={() => setPaymentMethod(m)} style={{ padding: '8px 4px', fontSize: '12px', border: '1px solid #e2e8f0', borderRadius: '6px', fontWeight: '600', backgroundColor: paymentMethod === m ? '#1e293b' : '#fff', color: paymentMethod === m ? '#fff' : '#1e293b', cursor: 'pointer' }}>{m}</button>
                              ))}
                            </div>
                            {paymentMethod !== 'Cash' && (
                              <input type="text" placeholder="Transaction Reference #" value={paymentReference} onChange={(e) => setPaymentReference(e.target.value)} style={styles.searchInput} />
                            )}
                          </div>
                          <div style={{ padding: '0 20px 20px 20px' }}>
                              <button onClick={handleProcessPayment} style={styles.primaryButton}>Confirm Payment</button>
                          </div>
                        </>
                      ) : (
                         <div style={{ padding: '20px', textAlign: 'center', background: '#f8fafc', color: '#64748b', fontSize: '12px', fontWeight: 'bold' }}>Order Complete</div>
                      )}
                    </motion.div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}><Receipt size={48} style={{ opacity: 0.2, marginBottom: '10px' }}/><p style={{ fontSize: '13px' }}>Select an order</p></div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
          `;

content = content.replace(oldOrdersBlock, newOrdersBlock);
fs.writeFileSync(file, content);
console.log('Orders block updated!');
