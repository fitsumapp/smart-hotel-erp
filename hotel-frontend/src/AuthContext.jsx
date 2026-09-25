import React, { createContext, useState, useEffect } from 'react';
import { clearSession, logoutSession } from './apiClient';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem('access_token'));

    useEffect(() => {
        if (token) {

            const savedUser = localStorage.getItem('user');
            if (savedUser) setUser(JSON.parse(savedUser));
        }
    }, [token]);

    const login = (userData, accessToken) => {
        setToken(accessToken);
        setUser(userData);
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('user', JSON.stringify(userData));

    };

    const logout = async () => {
        await logoutSession();
        clearSession();
        setToken(null);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, token, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
};