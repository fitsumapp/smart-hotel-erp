import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import {
  Mail, Lock, User, Phone, ArrowRight, ShieldCheck, RefreshCcw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from './apiConfig';
import { apiErrorMessage, clearSession, saveSession } from './apiClient';

const API_BASE = `${API_BASE_URL}/users/`;

const AuthPage = ({ onLoginSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isMfa, setIsMfa] = useState(false);
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
        clearSession();
        const res = await axios.post(`${API_BASE}${endpoint}`, {
          username: formData.email, password: formData.password
        });
        if (res.data.mfa_required) {
          setIsMfa(true);
          setIsVerifying(true);
          setFormData(previous => ({ ...previous, password: '', otp: '' }));
          setSuccess('Enter the login verification code sent to your email.');
        } else {
          saveSession(res.data);
          onLoginSuccess?.(res.data.user);
          navigate('/dashboard');
        }
      } else {
        setIsMfa(false);
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
      setError(apiErrorMessage(err, 'Authentication failed. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (isMfa) {
        const res = await axios.post(`${API_BASE}verify-mfa/`, { username: formData.email, code: formData.otp });
        saveSession(res.data);
        setIsMfa(false);
        setIsVerifying(false);
        onLoginSuccess?.(res.data.user);
        navigate('/dashboard');
      } else {
        await axios.post(`${API_BASE}verify-otp/`, { email: formData.email, otp: formData.otp });
        setSuccess('Account activated! You can now login with your password.');
        setIsVerifying(false);
        setIsLogin(true);
        setFormData(previous => ({ ...previous, otp: '' }));
      }
    } catch (err) {
      setError(apiErrorMessage(err, 'Invalid or expired code. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={containerStyle} className="auth-container">
      <div style={overlayStyle} className="auth-overlay"></div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        style={glassCardStyle}
        className="auth-glass-card"
      >
        <div style={headerSection}>
          <div style={logoBadgeStyle}>
            <ShieldCheck size={32} color="#3f5d45" />
          </div>
          <h1 style={mainTitleStyle}>ACRMA TECH</h1>
          <p style={subtitleStyle}>
            {isVerifying ? (isMfa ? "Verify Your Login" : "Verify Your Email") : isLogin ? "Welcome Back" : "Create New Account"}
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
              type="text" name="otp" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6}
              placeholder="OTP Code"
              value={formData.otp}
              onChange={handleInputChange}
            />
            <button type="submit" disabled={loading} style={submitBtnStyle}>
              {loading ? "Verifying..." : "Verify"}
            </button>
            <button type="button" onClick={() => { setIsVerifying(false); setIsMfa(false); setIsLogin(true); setError(''); setSuccess(''); }} style={cancelBtnStyle}>
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