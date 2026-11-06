import React, { useState } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../../services/api';
import './ChangePasswordModal.css';

const ChangePasswordModal = ({ isOpen, onClose }) => {
    const [formData, setFormData] = useState({
        oldPassword: '',
        newPassword: '',
        confirmPassword: ''
    });
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    if (!isOpen) return null;

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        setError('');
        setSuccess('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');

        // Validação client-side
        if (formData.newPassword !== formData.confirmPassword) {
            setError('As senhas não coincidem');
            return;
        }

        if (formData.newPassword.length < 8) {
            setError('A nova senha deve ter no mínimo 8 caracteres');
            return;
        }

        setIsLoading(true);

        try {
            const token = localStorage.getItem('token');
            await axios.post(
                `${API_BASE_URL}/api/auth/change-password/`,
                {
                    old_password: formData.oldPassword,
                    new_password: formData.newPassword
                },
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );

            setSuccess('Senha alterada com sucesso!');
            setFormData({ oldPassword: '', newPassword: '', confirmPassword: '' });

            setTimeout(() => {
                onClose();
            }, 2000);
        } catch (err) {
            if (err.response?.data?.error) {
                setError(err.response.data.error);
            } else if (err.response?.data?.old_password) {
                setError(err.response.data.old_password[0]);
            } else if (err.response?.data?.new_password) {
                setError(err.response.data.new_password[0]);
            } else {
                setError('Erro ao alterar senha. Tente novamente.');
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={(e) => {
            if (e.target.className === 'modal-overlay') onClose();
        }}>
            <div className="change-password-modal">
                <div className="modal-header">
                    <h2>Alterar Senha</h2>
                    <button className="close-btn" onClick={onClose}>&times;</button>
                </div>

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Senha Atual</label>
                        <input
                            type="password"
                            name="oldPassword"
                            value={formData.oldPassword}
                            onChange={handleChange}
                            required
                            disabled={isLoading}
                            placeholder="Digite sua senha atual"
                        />
                    </div>

                    <div className="form-group">
                        <label>Nova Senha</label>
                        <input
                            type="password"
                            name="newPassword"
                            value={formData.newPassword}
                            onChange={handleChange}
                            required
                            disabled={isLoading}
                            placeholder="Mínimo 8 caracteres"
                        />
                    </div>

                    <div className="form-group">
                        <label>Confirmar Nova Senha</label>
                        <input
                            type="password"
                            name="confirmPassword"
                            value={formData.confirmPassword}
                            onChange={handleChange}
                            required
                            disabled={isLoading}
                            placeholder="Digite novamente a nova senha"
                        />
                    </div>

                    {error && <div className="error-message">{error}</div>}
                    {success && <div className="success-message">{success}</div>}

                    <div className="modal-footer">
                        <button type="button" className="btn-cancel" onClick={onClose} disabled={isLoading}>
                            Cancelar
                        </button>
                        <button type="submit" className="btn-save" disabled={isLoading}>
                            {isLoading ? 'Alterando...' : 'Alterar Senha'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default ChangePasswordModal;
