import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import {
  Mail, Lock, User, Phone, ArrowRight, ShieldCheck,
  RefreshCcw, LogIn, UserPlus
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL, BASE_URL } from './apiConfig';

const API_BASE = `${API_BASE_URL}/users/`;

const AuthPage = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [isVerifying, setIsVerifying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    full_name: '', email: '', phone_number: '', password: '', otp: ''
  });

  const handleInputChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError("");
    setSuccess("");
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuccess("");

    const endpoint = isLogin ? 'login/' : 'register/';

    try {
      if (isLogin) {
        // --- 1. CLEAN SLATE: ማንኛውንም የቆየ ዳታ እና ቶከን እናጽዳ ---
        localStorage.clear();
        delete axios.defaults.headers.common["Authorization"];

        const loginData = {
          username: formData.email, // Django 'username' ብሎ ስለሚቀበል ኢሜይሉን እዚህ እንልካለን
          password: formData.password
        };

        // --- 2. ሪኩዌስት ስንልክ Headers ባዶ መሆኑን እናረጋግጥ ---
        const res = await axios.post(`${API_BASE}${endpoint}`, loginData, {
          headers: { 'Authorization': '' }
        });

        if (res.data.tokens && res.data.tokens.access) {
          // ቶከኖችን ማስቀመጥ
          localStorage.setItem('access_token', res.data.tokens.access);
          localStorage.setItem('refresh_token', res.data.tokens.refresh);
          localStorage.setItem('user', JSON.stringify(res.data.user));

          // አዲሱን ቶከን ለቀጣይ ሪኩዌስቶች Setup እናድርግ
          axios.defaults.headers.common["Authorization"] = `Bearer ${res.data.tokens.access}`;

          const user = res.data.user;
          const userRole = (user && user.role) ? user.role.toLowerCase().trim() : 'customer';

          // --- SMART REDIRECTION ---
          const currentHostname = window.location.hostname;
          const userTenant = user?.tenant_schema;

          if (userTenant && userTenant !== "public" && !user.is_platform_admin) {
              const targetSubdomain = userTenant.replace('hotel_', '').replace('hotel', '');
              
              if (!currentHostname.startsWith(targetSubdomain) && currentHostname !== targetSubdomain) {
                  const port = window.location.port ? `:${window.location.port}` : '';
                  const domainParts = currentHostname.split('.');
                  const baseDomain = domainParts.length > 1 ? domainParts.slice(-1)[0] : 'localhost';
                  
                  window.location.href = `${window.location.protocol}//${targetSubdomain}.${baseDomain}${port}/dashboard`;
                  return;
              }
          }
          navigate('/dashboard');
        }
      } else {
        const nameParts = formData.full_name.trim().split(' ');
        const registerData = {
          first_name: nameParts[0] || '',
          last_name: nameParts.slice(1).join(' ') || '',
          email: formData.email,
          phone_number: formData.phone_number,
          password: formData.password,
          username: formData.email.split('@')[0] || `user_${Date.now()}`
        };
        await axios.post(`${API_BASE}${endpoint}`, registerData);
        setSuccess("Registration successful! Code sent to your email.");
        setIsVerifying(true);
      }
    } catch (err) {
      console.error("Auth Error Details:", err.response?.data);
      const detail = err.response?.data?.detail || err.response?.data?.error;

      if (detail && (detail.includes("token") || detail.includes("credentials"))) {
        setError("Invalid email or password. Please try again.");
      } else {
        setError(detail || "Authentication failed. Please check your internet connection.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await axios.post(`${API_BASE}verify-otp/`, {
        email: formData.email,
        otp: formData.otp
      });

      setSuccess("Account activated! You can now login with your password.");
      setIsVerifying(false);
      setIsLogin(true);
      setFormData(prev => ({...prev, otp: ''}));

    } catch (err) {
      setError(err.response?.data?.error || "Invalid code. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={containerStyle}>
      <div style={overlayStyle}></div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        style={glassCardStyle}
      >
        <div style={headerSection}>
          <div style={logoBadgeStyle}>
            <ShieldCheck size={32} color="#3f5d45" />
          </div>
          <h1 style={mainTitleStyle}>ACRMA TECH</h1>
          <p style={subtitleStyle}>
            {isVerifying ? "Verify Your Email" : isLogin ? "Welcome Back" : "Create New Account"}
          </p>
        </div>

        {error && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={errorBoxStyle}>
            {error}
          </motion.div>
        )}
        {success && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={successBoxStyle}>
            {success}
          </motion.div>
        )}

        {!isVerifying ? (
          <form onSubmit={handleAuth} style={formStyle}>
            <AnimatePresence mode='wait'>
              {!isLogin && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  style={{overflow: 'hidden'}}
                  key="reg-fields"
                >
                  <InputWithIcon
                    icon={<User size={18} />}
                    type="text" name="full_name"
                    placeholder="Full Name"
                    value={formData.full_name}
                    onChange={handleInputChange}
                  />
                  <InputWithIcon
                    icon={<Phone size={18} />}
                    type="text" name="phone_number"
                    placeholder="Phone Number"
                    value={formData.phone_number}
                    onChange={handleInputChange}
                  />
                </motion.div>
              )}
            </AnimatePresence>

            <InputWithIcon
              icon={<Mail size={18} />}
              type="text" name="email"
              placeholder="Email or Username"
              value={formData.email}
              onChange={handleInputChange}
            />

            <InputWithIcon
              icon={<Lock size={18} />}
              type="password" name="password"
              placeholder="Password"
              value={formData.password}
              onChange={handleInputChange}
            />

            <button type="submit" disabled={loading} style={submitBtnStyle}>
              {loading ? <RefreshCcw className="animate-spin" size={20} /> : (
                <>{isLogin ? "Login" : "Register"} <ArrowRight size={18} style={{marginLeft: '8px'}} /></>
              )}
            </button>

            <div style={toggleContainerStyle}>
              <span style={{color: '#64748b', fontSize: '14px'}}>
                {isLogin ? "Don't have an account?" : "Already have an account?"}
              </span>
              <button
                type="button"
                onClick={() => setIsLogin(!isLogin)}
                style={toggleBtnStyle}
              >
                {isLogin ? "Register" : "Login"}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleVerifyOTP} style={formStyle}>
            <p style={{textAlign: 'center', fontSize: '13px', color: '#64748b', marginBottom: '20px'}}>
               Enter the 6-digit code sent to {formData.email}.
            </p>
            <InputWithIcon
              icon={<ShieldCheck size={18} />}
              type="text" name="otp"
              placeholder="OTP Code"
              value={formData.otp}
              onChange={handleInputChange}
            />
            <button type="submit" disabled={loading} style={submitBtnStyle}>
              {loading ? "Verifying..." : "Verify"}
            </button>
            <button type="button" onClick={() => setIsVerifying(false)} style={cancelBtnStyle}>
              Back to Login
            </button>
          </form>
        )}
      </motion.div>

      <div style={footerNoteStyle}>© 2026 ACRMA TECH SOLUTION. All Rights Reserved.</div>
    </div>
  );
};

// Helper Components & Styles
const InputWithIcon = ({ icon, ...props }) => (
  <div style={inputWrapperStyle}>
    <div style={iconBoxStyle}>{icon}</div>
    <input style={inputStyle} required {...props} />
  </div>
);

const containerStyle = {
  height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
  backgroundImage: 'url("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTlQC5gwoJtk52KRAyRal3FirEA2cYJ1OLczQ&s")',
  backgroundSize: 'cover', backgroundPosition: 'center', fontFamily: "'Inter', sans-serif", position: 'relative', overflow: 'hidden'
};

const overlayStyle = { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0, 0, 0, 0.4)', backdropFilter: 'blur(3px)', zIndex: 1 };
const glassCardStyle = { backgroundColor: 'rgba(255, 255, 255, 0.9)', padding: '40px', borderRadius: '30px', width: '100%', maxWidth: '440px', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)', zIndex: 2, border: '1px solid rgba(255, 255, 255, 0.3)' };
const headerSection = { textAlign: 'center', marginBottom: '30px' };
const logoBadgeStyle = { width: '64px', height: '64px', backgroundColor: '#f1f5f9', borderRadius: '18px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 15px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)' };
const mainTitleStyle = { fontSize: '26px', fontWeight: '800', color: '#1e293b', margin: '0', letterSpacing: '-0.5px' };
const subtitleStyle = { color: '#64748b', fontSize: '15px', marginTop: '5px' };
const formStyle = { display: 'flex', flexDirection: 'column', gap: '18px' };
const inputWrapperStyle = { display: 'flex', alignItems: 'center', backgroundColor: '#f8fafc', borderRadius: '14px', padding: '12px 16px', border: '1px solid #e2e8f0', transition: 'all 0.2s', marginBottom: '5px' };
const iconBoxStyle = { color: '#94a3b8', marginRight: '12px', display: 'flex', alignItems: 'center' };
const inputStyle = { border: 'none', background: 'none', outline: 'none', width: '100%', fontSize: '14px', color: '#1e293b' };
const submitBtnStyle = { backgroundColor: '#3f5d45', color: 'white', padding: '14px', borderRadius: '14px', border: 'none', fontSize: '16px', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 10px 15px -3px rgba(63, 93, 69, 0.4)', marginTop: '15px', transition: 'all 0.2s' };
const errorBoxStyle = { backgroundColor: '#fef2f2', color: '#ef4444', padding: '12px', borderRadius: '10px', fontSize: '13px', textAlign: 'center', marginBottom: '15px', border: '1px solid #fee2e2' };
const successBoxStyle = { backgroundColor: '#ecfdf5', color: '#10b981', padding: '12px', borderRadius: '10px', fontSize: '13px', textAlign: 'center', marginBottom: '15px', border: '1px solid #d1fae5' };
const toggleContainerStyle = { textAlign: 'center', marginTop: '25px', display: 'flex', justifyContent: 'center', gap: '8px', alignItems: 'center' };
const toggleBtnStyle = { background: 'none', border: 'none', color: '#3f5d45', fontWeight: '700', cursor: 'pointer', fontSize: '14px' };
const cancelBtnStyle = { background: 'none', border: 'none', color: '#64748b', marginTop: '15px', cursor: 'pointer', fontSize: '14px' };
const footerNoteStyle = { position: 'absolute', bottom: '25px', color: '#fff', fontSize: '12px', fontWeight: '600', zIndex: 2, letterSpacing: '1px' };

export default AuthPage;