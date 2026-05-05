async function refreshStats() {
    try {
        // API üzerinden durum verilerinin çekilmesi
        const response = await fetch('http://localhost:5000/api/status?t=' + new Date().getTime());
        const data = await response.json();

        // Gelen verilerin konsol tablosu
        console.table(data);

        const tableBody = document.getElementById('monitor-table');
        if (!tableBody) return;
        
        // Tablo içeriğinin temizlenmesi
        tableBody.innerHTML = '';

        data.forEach(item => {
            // Zaman verisi kontrolü ve ataması
            let displayTime = item.checked_at || item.last_check || "--:--:--";

            if (displayTime === "undefined") {
                console.error("Zaman verisi hatası:", item);
            }

            // Yanıt süresi formatlama
            let respTime = item.response_time ? parseFloat(item.response_time).toFixed(3) + " sn" : "0.000 sn";
            
            // HTTP koduna göre sağlık durumu tespiti
            const isHealthy = item.status >= 200 && item.status < 300;

            // Tablo satırı oluşturma ve ekleme işlemi
            tableBody.innerHTML += `
                <tr>
                    <td class="px-4"><strong>${item.url}</strong></td>
                    <td><span class="badge ${isHealthy ? 'bg-success' : 'bg-danger'}">${isHealthy ? 'Sağlıklı' : 'Çöktü'}</span></td>
                    <td><code>${item.status}</code></td>
                    <td><small>${respTime}</small></td>
                    <td><span class="badge bg-dark">${item.total_failures || 0}</span></td>
                    <td><small class="text-secondary">${displayTime}</small></td>
                </tr>
            `;
        });
    } catch (e) { 
        // Bağlantı ve API hatası kaydı
        console.error("Bağlantı hatası:", e); 
    }
}
