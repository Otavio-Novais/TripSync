import React, { useState, useEffect } from 'react';
import { X, Calendar, User, FileText, Check, ChevronDown, MapPin, Loader2 } from 'lucide-react';
import CustomDatePicker from './common/CustomDatePicker';
import tripsApi from '../services/tripsApi';
import '../pages/Finance/Finance.css';

const AddExpenseModal = ({ viagemId, onClose, onSuccess }) => {
    const [loading, setLoading] = useState(true);
    const [participantes, setParticipantes] = useState([]);
    const [trips, setTrips] = useState([]);
    const [selectedTripId, setSelectedTripId] = useState(viagemId || '');
    const [error, setError] = useState(null);

    // States do Formulário
    const [titulo, setTitulo] = useState('');
    const [valorTotal, setValorTotal] = useState('');
    const [pagadorId, setPagadorId] = useState('');
    const [data, setData] = useState(new Date().toISOString().split('T')[0]);
    const [notas, setNotas] = useState('');

    // States do Rateio
    const [modoDivisao, setModoDivisao] = useState('IGUAL'); // IGUAL, EXATO, PERCENTUAL
    const [selecionados, setSelecionados] = useState([]);
    const [valoresManuais, setValoresManuais] = useState({});

    // Fetch Trips para o seletor
    useEffect(() => {
        tripsApi.listarViagens()
            .then(data => {
                setTrips(data);
                if (!selectedTripId && data.length > 0) {
                    setSelectedTripId(data[0].id);
                }
            })
            .catch(err => {
                console.error("Erro ao carregar viagens:", err);
                if (err.message.includes('Sessão expirada')) {
                    alert("Sua sessão expirou. Por favor, faça login novamente.");
                }
            });
    }, [selectedTripId]);

    // Fetch Participantes quando a viagem selecionada muda
    useEffect(() => {
        if (!selectedTripId) return;
        setLoading(true);
        setError(null);
        tripsApi.obterFinancas(selectedTripId)
            .then(d => {
                const users = d.resumo.map(u => ({ id: u.id, nome: u.nome, avatar: u.nome.charAt(0) }));
                setParticipantes(users);
                setSelecionados(users.map(u => u.id));
                if (users.length > 0) setPagadorId(users[0].id);
                setLoading(false);
            })
            .catch(err => {
                console.error("Erro ao carregar participantes:", err);
                setError("Não foi possível carregar os participantes da viagem.");
                setLoading(false);
            });
    }, [selectedTripId]);

    // Handlers
    const toggleSelecionado = (id) => {
        if (selecionados.includes(id)) setSelecionados(selecionados.filter(s => s !== id));
        else setSelecionados([...selecionados, id]);
    };

    const handleManualChange = (id, val) => {
        setValoresManuais({ ...valoresManuais, [id]: val });
    };

    const handleSubmit = async (e, isDraft = false) => { // Recebe flag se é rascunho
        e.preventDefault();
        const total = parseFloat(valorTotal) || 0;

        // Se for rascunho, validação é mais leve
        if (!isDraft && (!valorTotal || selecionados.length === 0)) {
            alert("Para lançar, preencha o valor e a divisão.");
            return;
        }
        let rateios = [];

        if (modoDivisao === 'IGUAL') {
            const valor = total / selecionados.length;
            rateios = selecionados.map(uid => ({ user_id: uid, valor: valor.toFixed(2) }));
        } else if (modoDivisao === 'EXATO') {
            rateios = Object.keys(valoresManuais).map(uid => ({ user_id: parseInt(uid), valor: parseFloat(valoresManuais[uid]).toFixed(2) }));
        } else { // PERCENTUAL
            rateios = Object.keys(valoresManuais).map(uid => ({
                user_id: parseInt(uid),
                valor: ((total * parseFloat(valoresManuais[uid])) / 100).toFixed(2)
            }));
        }

        try {
            await tripsApi.criarDespesa(selectedTripId, {
                titulo,
                valor_total: total,
                pagador_id: pagadorId,
                data,
                rateios,
                status: isDraft ? 'RASCUNHO' : 'CONFIRMADO'
            });
            onSuccess();
            onClose();
        } catch (err) { alert("Erro ao salvar"); }
    };

    // Cálculos visuais
    const totalNum = parseFloat(valorTotal) || 0;
    const valorPorPessoa = selecionados.length ? (totalNum / selecionados.length).toFixed(2) : '0.00';
    const somaAtual = modoDivisao === 'EXATO'
        ? Object.values(valoresManuais).reduce((a, b) => a + (parseFloat(b) || 0), 0)
        : modoDivisao === 'PERCENTUAL'
            ? Object.values(valoresManuais).reduce((a, b) => a + (parseFloat(b) || 0), 0)
            : 0;

    return (
        <div className="modal-overlay">
            <div className="modal-content" style={{ maxWidth: '700px', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>

                {/* HEADER CUSTOM */}
                <div className="modal-header-custom">
                    <span className="modal-title">Adicionar Despesa</span>
                    <button type="button" onClick={onClose} className="btn-close-ghost">
                        <X size={16} /> Fechar
                    </button>
                </div>

                {/* LOADING STATE */}
                {loading && !participantes.length ? (
                    <div style={{ 
                        display: 'flex', 
                        flexDirection: 'column', 
                        alignItems: 'center', 
                        justifyContent: 'center', 
                        padding: '4rem 2rem',
                        gap: '1rem'
                    }}>
                        <Loader2 size={40} className="animate-spin" style={{ color: '#0066FF' }} />
                        <p style={{ color: '#6B7280', fontSize: '14px', margin: 0 }}>
                            Carregando dados da viagem...
                        </p>
                    </div>
                ) : error ? (
                    /* ERROR STATE */
                    <div style={{ 
                        display: 'flex', 
                        flexDirection: 'column', 
                        alignItems: 'center', 
                        justifyContent: 'center', 
                        padding: '4rem 2rem',
                        gap: '1rem'
                    }}>
                        <div style={{ 
                            width: '60px', 
                            height: '60px', 
                            borderRadius: '50%', 
                            background: '#FEF2F2', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            fontSize: '30px'
                        }}>
                            ⚠️
                        </div>
                        <p style={{ color: '#EF4444', fontSize: '14px', margin: 0, fontWeight: 600 }}>
                            {error}
                        </p>
                        <button 
                            onClick={() => window.location.reload()} 
                            className="btn-primary"
                            style={{ marginTop: '1rem' }}
                        >
                            Tentar Novamente
                        </button>
                    </div>
                ) : (
                    /* FORMULÁRIO */
                    <form onSubmit={handleSubmit} className="expense-form-container">
                        <div className="expense-scroll-body">

                        {/* SELETOR DE VIAGEM */}
                        <div style={{ marginBottom: 20 }}>
                            <label className="pill-label">Viagem</label>
                            <div className="pill-input-group">
                                <MapPin size={18} className="pill-icon" />
                                <select
                                    className="pill-input"
                                    value={selectedTripId}
                                    onChange={e => setSelectedTripId(e.target.value)}
                                >
                                    {trips.map(t => (
                                        <option key={t.id} value={t.id}>{t.titulo}</option>
                                    ))}
                                </select>
                                <ChevronDown size={16} style={{ position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)', color: '#94A3B8', pointerEvents: 'none' }} />
                            </div>
                        </div>

                        {/* Linha 1 */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 20, marginBottom: 20 }}>
                            <div>
                                <label className="pill-label">Descrição</label>
                                <div className="pill-input-group">
                                    <input className="pill-input" placeholder="Ex.: Hospedagem" value={titulo} onChange={e => setTitulo(e.target.value)} required />
                                </div>
                            </div>
                            <div>
                                <label className="pill-label">Valor Total</label>
                                <div className="pill-input-group">
                                    <input type="number" step="0.01" className="pill-input" placeholder="0,00" value={valorTotal} onChange={e => setValorTotal(e.target.value)} required />
                                </div>
                            </div>
                        </div>

                        {/* Linha 2 */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 32 }}>
                            <div>
                                <label className="pill-label">Quem Pagou</label>
                                <div className="pill-input-group">
                                    <User size={18} className="pill-icon" />
                                    <select className="pill-input" value={pagadorId} onChange={e => setPagadorId(e.target.value)}>
                                        {participantes.map(p => <option key={p.id} value={p.id}>{p.nome}</option>)}
                                    </select>
                                    <ChevronDown size={16} style={{ position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)', color: '#94A3B8', pointerEvents: 'none' }} />
                                </div>
                            </div>
                            <div>
                                <label className="pill-label">Data</label>
                                <div className="pill-input-group">
                                    <Calendar size={18} className="pill-icon" />
                                    <CustomDatePicker
                                        selected={data ? new Date(data + 'T12:00:00') : null}
                                        onChange={(date) => {
                                            const formattedDate = date ? date.toISOString().split('T')[0] : '';
                                            setData(formattedDate);
                                        }}
                                        placeholder="Data da despesa"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Abas */}
                        <label className="pill-label">Como dividir?</label>
                        <div className="division-tabs">
                            <button type="button" className={`div-tab ${modoDivisao === 'IGUAL' ? 'active' : ''}`} onClick={() => setModoDivisao('IGUAL')}>Igualmente</button>
                            <button type="button" className={`div-tab ${modoDivisao === 'EXATO' ? 'active' : ''}`} onClick={() => setModoDivisao('EXATO')}>Por Valor</button>
                            <button type="button" className={`div-tab ${modoDivisao === 'PERCENTUAL' ? 'active' : ''}`} onClick={() => setModoDivisao('PERCENTUAL')}>Percentual</button>
                        </div>

                        {/* Lista de Pessoas (Azul) */}
                        <div className="participants-blue-box">
                            {participantes.map(p => {
                                const isSelected = selecionados.includes(p.id);
                                return (
                                    <div key={p.id} className="user-pill-row">
                                        <div className="u-info">
                                            <img src={`https://ui-avatars.com/api/?name=${p.nome}&background=random`} className="u-avatar" alt="" />
                                            <div className="u-name-box">
                                                <span>{p.nome}</span>
                                                <span className="u-role">Participante</span>
                                            </div>
                                        </div>

                                        {modoDivisao === 'IGUAL' && (
                                            <button type="button" className={`btn-select ${isSelected ? 'selected' : 'unselected'}`} onClick={() => toggleSelecionado(p.id)}>
                                                {isSelected ? 'Selecionado' : 'Selecionar'}
                                            </button>
                                        )}
                                        {modoDivisao === 'EXATO' && (
                                            <div className="small-input-wrapper">
                                                <span style={{ fontSize: 12, color: '#9CA3AF' }}>R$</span>
                                                <input type="number" className="small-input" placeholder="0,00" onChange={e => handleManualChange(p.id, e.target.value)} />
                                            </div>
                                        )}
                                        {modoDivisao === 'PERCENTUAL' && (
                                            <div className="small-input-wrapper">
                                                <input type="number" className="small-input" placeholder="0" onChange={e => handleManualChange(p.id, e.target.value)} />
                                                <span style={{ fontSize: 12, color: '#9CA3AF' }}>%</span>
                                            </div>
                                        )}
                                    </div>
                                )
                            })}

                            <div className="blue-box-footer">
                                {modoDivisao === 'IGUAL' && <span>{selecionados.length} pessoas dividindo</span>}
                                {modoDivisao === 'EXATO' && <span>Confira o total</span>}
                                {modoDivisao === 'PERCENTUAL' && <span>Confira a %</span>}

                                <span className="total-display">
                                    {modoDivisao === 'IGUAL' ? `R$ ${valorPorPessoa}/pessoa` :
                                        modoDivisao === 'EXATO' ? `Total: R$ ${somaAtual.toFixed(2)}` : `Total: ${somaAtual}%`}
                                </span>
                            </div>
                        </div>

                        {/* Notas */}
                        <label className="pill-label">Observações</label>
                        <div className="pill-input-group" style={{ marginBottom: 20 }}>
                            <input className="pill-input" placeholder="Adicionar notas..." value={notas} onChange={e => setNotas(e.target.value)} />
                        </div>
                    </div>

                        {/* Footer Buttons */}
                        <div className="modal-footer">
                            <button type="button" onClick={onClose} className="btn-close-ghost">Cancelar</button>
                            <div style={{ display: 'flex', gap: 12 }}>
                                {/* Botão Rascunho */}
                                <button type="button" onClick={(e) => handleSubmit(e, true)} className="btn-close-ghost" style={{ color: '#0066FF', background: '#EFF6FF' }}>
                                    <FileText size={16} /> Salvar Rascunho
                                </button>
                                {/* Botão Lançar */}
                                <button type="submit" onClick={(e) => handleSubmit(e, false)} className="btn-big-blue">
                                    <Check size={18} style={{ marginRight: 6 }} /> Lançar Despesa
                                </button>
                            </div>
                        </div>
                    </form>
                )}
            </div>
        </div>
    );
};

export default AddExpenseModal;
