import React, { useEffect, useState } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { Share2, Settings, MapPin } from 'lucide-react';
import { API_BASE_URL } from '../../services/api';

const DashboardHeader = () => {
  const { tripId } = useParams();
  const location = useLocation();
  const [tripData, setTripData] = useState(null);

  // Determina o título com base na rota se não estiver em uma viagem específica
  const getPageTitle = () => {
    if (location.pathname === '/dashboard') return 'Minhas Viagens';
    if (location.pathname === '/profile') return 'Meu Perfil';
    if (location.pathname === '/settings') return 'Configurações';
    return 'Tripsync';
  };

  useEffect(() => {
    if (tripId) {
      fetch(`${API_BASE_URL}/planner/api/viagem/${tripId}/`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      })
        .then(res => res.json())
        .then(data => setTripData(data))
        .catch(err => console.error("Erro ao carregar header:", err));
    } else {
      setTripData(null);
    }
  }, [tripId]);

  return (
    <div style={{
      backgroundColor: 'white',
      borderBottom: '1px solid #f3f4f6',
      padding: '1rem 2rem',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      height: '64px', // Altura fixa para alinhar
      boxSizing: 'border-box'
    }}>
      {/* Lado Esquerdo: Título Contextual */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {tripId && tripData ? (
          <>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              backgroundColor: '#eff6ff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#2563eb',
            }}>
              <MapPin size={20} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.1rem', fontWeight: '700', color: '#111827', margin: 0 }}>
                {tripData.title}
              </h1>
              <div style={{ fontSize: '0.8rem', color: '#6b7280', display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span>{new Date(tripData.start_date).toLocaleDateString()}</span>
                <span style={{ width: 4, height: 4, background: '#d1d5db', borderRadius: '50%' }}></span>
                <span>Planejamento</span>
              </div>
            </div>
          </>
        ) : (
          <h1 style={{ fontSize: '1.5rem', fontWeight: '700', color: '#111827', margin: 0 }}>
            {getPageTitle()}
          </h1>
        )}
      </div>

      {/* Lado Direito: Ações Globais ou da Viagem */}
      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>



        {tripId && (
          <>
            <div style={{ width: 1, height: 24, background: '#e5e7eb' }}></div>

            <button
              onClick={() => {
                navigator.clipboard.writeText(window.location.href);
                alert('Link da viagem copiado para a área de transferência!');
              }}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                backgroundColor: 'transparent', color: '#4b5563', border: '1px solid #e5e7eb',
                padding: '0.5rem 1rem', borderRadius: '8px', fontWeight: '500', fontSize: '0.85rem', cursor: 'pointer'
              }}
            >
              <Share2 size={16} /> Compartilhar
            </button>

            <button style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              backgroundColor: 'transparent', color: '#4b5563', border: '1px solid #e5e7eb',
              padding: '0.5rem 1rem', borderRadius: '8px', fontWeight: '500', fontSize: '0.85rem', cursor: 'pointer'
            }}>
              <Settings size={16} /> Ajustes
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default DashboardHeader;
