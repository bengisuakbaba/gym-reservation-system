class ReservationNotificationManager {
    constructor() {
        this.checkInterval = null;
        this.notifiedReservations = new Set();
        this.notifiedQueueReservations = new Set();
        this.audioEnabled = false;
        this.requestNotificationPermission();
        this.initAudioForAndroid();
    }

    initAudioForAndroid() {
        if (/Android.*Chrome/i.test(navigator.userAgent)) {
            const enableAudio = () => {
                try {
                    const audio = new Audio();
                    audio.volume = 0.01;
                    audio.src = 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBjuNzvLNeSsF';

                    audio.play().then(() => {
                        this.audioEnabled = true;
                        audio.volume = 0;
                        audio.pause();
                    }).catch(() => {
                        this.audioEnabled = false;
                    });
                } catch (error) {
                    this.audioEnabled = false;
                }

                document.removeEventListener('touchstart', enableAudio);
                document.removeEventListener('click', enableAudio);
            };

            document.addEventListener('touchstart', enableAudio, { once: true });
            document.addEventListener('click', enableAudio, { once: true });
        }
    }

    async requestNotificationPermission() {
        if ('Notification' in window) {
            if (Notification.permission === 'default') {
                if (/Android.*Chrome/i.test(navigator.userAgent)) {
                    setTimeout(async () => {
                        try {
                            await Notification.requestPermission();
                        } catch (error) {
                            console.log('Notification permission request failed');
                        }
                    }, 2000);
                } else {
                    await Notification.requestPermission();
                }
            }
        }
    }

    startMonitoring(reservations) {
        if (!reservations || reservations.length === 0) {
            return;
        }

        if (this.checkInterval) {
            clearInterval(this.checkInterval);
        }

        this.checkInterval = setInterval(() => {
            this.checkReservations(reservations);
        }, 30000);

        this.checkReservations(reservations);
    }

    checkReservations(reservations) {
        const now = new Date();

        reservations.forEach(reservation => {
            if (reservation.queue_position === 0) {
                const endTime = new Date(reservation.end_time);
                const timeDiff = endTime - now;
                const minutesLeft = Math.floor(timeDiff / (1000 * 60));

                if (minutesLeft === 1 && !this.notifiedReservations.has(reservation.id)) {
                    this.showEndTimeNotification(reservation);
                    this.notifiedReservations.add(reservation.id);
                }

                if (timeDiff <= 0) {
                    this.notifiedReservations.delete(reservation.id);
                }
            }

            if (reservation.queue_position === 1) {
                const startTime = new Date(reservation.start_time);
                const timeDiff = startTime - now;
                const minutesUntilTurn = Math.floor(timeDiff / (1000 * 60));

                if (minutesUntilTurn === 1 && !this.notifiedQueueReservations.has(reservation.id)) {
                    this.showQueueNotification(reservation);
                    this.notifiedQueueReservations.add(reservation.id);
                }

                if (minutesUntilTurn === 0 && !this.notifiedQueueReservations.has(`${reservation.id}_ready`)) {
                    this.showTurnReadyNotification(reservation);
                    this.notifiedQueueReservations.add(`${reservation.id}_ready`);
                }

                if (timeDiff <= -60000) {
                    this.notifiedQueueReservations.delete(reservation.id);
                    this.notifiedQueueReservations.delete(`${reservation.id}_ready`);
                }
            }
        });
    }

    showEndTimeNotification(reservation) {
        const message = `Your ${reservation.equipment_name} session will end in 1 minute`;

        if ('Notification' in window && Notification.permission === 'granted') {
            const notification = new Notification('Session Ending Soon', {
                body: message,
                tag: `reservation-${reservation.id}`,
                icon: '/static/images/warning-icon.png',
                requireInteraction: true
            });

            notification.onclick = () => {
                window.focus();
                notification.close();
            };

            setTimeout(() => {
                notification.close();
            }, 10000);
        }

        this.showModalWarning(message, 'Session Ending Soon', 'warning');

        this.playNotificationSound();
    }

    showQueueNotification(reservation) {
        const message = `Get ready! Your turn for ${reservation.equipment_name} is in 1 minute`;

        if ('Notification' in window && Notification.permission === 'granted') {
            const notification = new Notification('Your Turn is Coming', {
                body: message,
                tag: `queue-${reservation.id}`,
                icon: '/static/images/queue-icon.png',
                requireInteraction: true
            });

            notification.onclick = () => {
                window.focus();
                notification.close();
            };

            setTimeout(() => {
                notification.close();
            }, 10000);
        }

        this.showModalWarning(message, 'Get Ready!', 'info');

        this.playNotificationSound();
    }

    showTurnReadyNotification(reservation) {
        const message = `It's your turn! ${reservation.equipment_name} is now available for you`;

        if ('Notification' in window && Notification.permission === 'granted') {
            const notification = new Notification('Your Turn Now!', {
                body: message,
                tag: `ready-${reservation.id}`,
                icon: '/static/images/ready-icon.png',
                requireInteraction: true
            });

            notification.onclick = () => {
                window.focus();
                notification.close();
            };

            setTimeout(() => {
                notification.close();
            }, 15000);
        }

        this.showModalWarning(message, 'Your Turn Now!', 'success');

        this.playNotificationSound();
        setTimeout(() => this.playNotificationSound(), 500);
    }

    showModalWarning(message, title = 'Notification', type = 'warning') {
        const existingModals = document.querySelectorAll('.reservation-modal');
        existingModals.forEach(modal => modal.remove());

        let headerGradient, iconClass;
        switch(type) {
            case 'warning':
                headerGradient = 'linear-gradient(135deg, #ff6b35, #f7931e)';
                iconClass = 'fas fa-exclamation-triangle';
                break;
            case 'info':
                headerGradient = 'linear-gradient(135deg, #667eea, #764ba2)';
                iconClass = 'fas fa-info-circle';
                break;
            case 'success':
                headerGradient = 'linear-gradient(135deg, #11998e, #38ef7d)';
                iconClass = 'fas fa-check-circle';
                break;
            default:
                headerGradient = 'linear-gradient(135deg, #ff6b35, #f7931e)';
                iconClass = 'fas fa-bell';
        }

        const modalOverlay = document.createElement('div');
        modalOverlay.className = 'reservation-modal';
        modalOverlay.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content">
                <div class="modal-header" style="background: ${headerGradient};">
                    <i class="${iconClass}" style="margin-right: 10px; font-size: 1.2em;"></i>
                    <h3>${title}</h3>
                </div>
                <div class="modal-body">
                    <p>${message}</p>
                    <p class="modal-subtitle">Please check your reservations page for more details.</p>
                </div>
                <div class="modal-footer">
                    <button class="modal-close-btn">I Understand</button>
                </div>
            </div>
        `;

        document.body.appendChild(modalOverlay);

        document.body.style.overflow = 'hidden';

        const closeBtn = modalOverlay.querySelector('.modal-close-btn');
        const overlay = modalOverlay.querySelector('.modal-overlay');

        const closeModal = () => {
            modalOverlay.classList.add('fade-out');
            document.body.style.overflow = '';
            setTimeout(() => {
                if (modalOverlay.parentNode) {
                    modalOverlay.remove();
                }
            }, 300);
        };

        closeBtn.addEventListener('click', closeModal);

        overlay.addEventListener('click', (e) => {
            e.preventDefault();
            modalOverlay.querySelector('.modal-content').classList.add('shake');
            setTimeout(() => {
                modalOverlay.querySelector('.modal-content').classList.remove('shake');
            }, 600);

            if (/Android.*Chrome/i.test(navigator.userAgent)) {
                this.playAndroidSafeSound();
            }
        });

        setTimeout(() => {
            if (/Android.*Chrome/i.test(navigator.userAgent)) {
                this.playAndroidSafeSound();
            }
        }, 200);

        setTimeout(() => {
            modalOverlay.classList.add('show');
        }, 50);

        const autoCloseTime = type === 'success' ? 20000 : 15000;
        setTimeout(() => {
            if (modalOverlay.parentNode) {
                closeModal();
            }
        }, autoCloseTime);
    }

    playNotificationSound() {
        const isAndroidChrome = /Android.*Chrome/i.test(navigator.userAgent);

        if (isAndroidChrome) {
            this.playAndroidSafeSound();
        } else {
            this.playHighQualitySound();
        }
    }

    playHighQualitySound() {
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();

            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(800, audioContext.currentTime);

            gainNode.gain.setValueAtTime(0, audioContext.currentTime);
            gainNode.gain.linearRampToValueAtTime(0.3, audioContext.currentTime + 0.01);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);

            setTimeout(() => {
                const oscillator2 = audioContext.createOscillator();
                const gainNode2 = audioContext.createGain();

                oscillator2.connect(gainNode2);
                gainNode2.connect(audioContext.destination);

                oscillator2.type = 'sine';
                oscillator2.frequency.setValueAtTime(1000, audioContext.currentTime);

                gainNode2.gain.setValueAtTime(0, audioContext.currentTime);
                gainNode2.gain.linearRampToValueAtTime(0.25, audioContext.currentTime + 0.01);
                gainNode2.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);

                oscillator2.start(audioContext.currentTime);
                oscillator2.stop(audioContext.currentTime + 0.3);
            }, 200);

        } catch (error) {
            console.log('Web Audio API failed, using fallback');
            this.playFallbackSound();
        }
    }

    playFallbackSound() {
        try {
            const audio = new Audio();
            audio.volume = 0.7;

            audio.src = 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBjuNzvLNeSsF';

            const playPromise = audio.play();

            if (playPromise !== undefined) {
                playPromise.then(() => {
                    setTimeout(() => {
                        const audio2 = new Audio();
                        audio2.volume = 0.6;
                        audio2.src = audio.src;
                        audio2.play().catch(() => {});
                    }, 300);
                }).catch(() => {
                    this.tryVibration();
                });
            }
        } catch (error) {
            this.tryVibration();
        }
    }

    playAndroidSafeSound() {
        try {
            if (!this.audioEnabled) {
                this.tryVibration();
                return;
            }

            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();

                if (audioContext.state === 'suspended') {
                    audioContext.resume().then(() => {
                        this.createAndroidNotificationSound(audioContext);
                    });
                } else {
                    this.createAndroidNotificationSound(audioContext);
                }
            } catch (audioContextError) {
                this.playFallbackSound();
            }
        } catch (error) {
            this.tryVibration();
        }
    }

    createAndroidNotificationSound(audioContext) {
        try {
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(750, audioContext.currentTime);

            gainNode.gain.setValueAtTime(0, audioContext.currentTime);
            gainNode.gain.linearRampToValueAtTime(0.4, audioContext.currentTime + 0.02);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.6);

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.6);

            setTimeout(() => {
                const oscillator2 = audioContext.createOscillator();
                const gainNode2 = audioContext.createGain();

                oscillator2.connect(gainNode2);
                gainNode2.connect(audioContext.destination);

                oscillator2.type = 'sine';
                oscillator2.frequency.setValueAtTime(900, audioContext.currentTime);

                gainNode2.gain.setValueAtTime(0, audioContext.currentTime);
                gainNode2.gain.linearRampToValueAtTime(0.35, audioContext.currentTime + 0.02);
                gainNode2.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.4);

                oscillator2.start(audioContext.currentTime);
                oscillator2.stop(audioContext.currentTime + 0.4);
            }, 250);

        } catch (error) {
            this.playFallbackSound();
        }
    }

    tryVibration() {
        try {
            if ('vibrate' in navigator) {
                navigator.vibrate([600, 300, 600, 300, 800]);

                setTimeout(() => {
                    navigator.vibrate([500, 200, 500]);
                }, 2000);
            }
        } catch (error) {
            console.log('Vibration not supported');
        }
    }

    stopMonitoring() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }
        this.notifiedReservations.clear();
        this.notifiedQueueReservations.clear();
    }
}

window.reservationNotificationManager = new ReservationNotificationManager();

document.addEventListener('DOMContentLoaded', function() {
    const mobileToggle = document.querySelector('.mobile-toggle');
    const mainNav = document.querySelector('.main-nav');

    if (mobileToggle && mainNav) {
        mobileToggle.addEventListener('click', function() {
            mainNav.classList.toggle('active');
            this.classList.toggle('active');
        });
    }

    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    if (tabButtons.length > 0 && tabContents.length > 0) {
        tabButtons.forEach(button => {
            button.addEventListener('click', function() {
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));

                this.classList.add('active');

                const tabId = this.getAttribute('data-tab');
                document.getElementById(tabId + '-tab').classList.add('active');
            });
        });
    }

    const filterButtons = document.querySelectorAll('.filter-btn');
    const equipmentCards = document.querySelectorAll('.equipment-card');

    if (filterButtons.length > 0 && equipmentCards.length > 0) {
        filterButtons.forEach(button => {
            button.addEventListener('click', function() {
                filterButtons.forEach(btn => btn.classList.remove('active'));

                this.classList.add('active');

                const filterType = this.getAttribute('data-filter');

                equipmentCards.forEach(card => {
                    if (filterType === 'all') {
                        card.style.display = 'block';
                    } else if (card.classList.contains(filterType)) {
                        card.style.display = 'block';
                    } else {
                        card.style.display = 'none';
                    }
                });
            });
        });
    }

    const alerts = document.querySelectorAll('.alert');

    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.style.display = 'none';
            }, 500);
        }, 5000);
    });
});

function startReservationMonitoring(reservations) {
    if (window.reservationNotificationManager) {
        window.reservationNotificationManager.startMonitoring(reservations);
    }
}

function stopReservationMonitoring() {
    if (window.reservationNotificationManager) {
        window.reservationNotificationManager.stopMonitoring();
    }
}