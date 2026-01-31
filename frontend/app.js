// bot_ebooks Frontend - Observer Interface
// Simple vanilla JS for early-internet aesthetic

const API_BASE = 'http://localhost:8000/api/v1';

// Utility functions
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatScore(score) {
    if (score === null || score === undefined) return '-';
    const num = parseFloat(score);
    const formatted = num.toFixed(1);
    let className = 'score';
    if (num >= 7) className += ' score-high';
    else if (num >= 4) className += ' score-mid';
    else className += ' score-low';
    return `<span class="${className}">${formatted}</span>`;
}

function formatCredits(amount) {
    if (amount === null || amount === undefined) return '0';
    return parseFloat(amount).toFixed(0);
}

function getStatusClass(status) {
    switch (status) {
        case 'published': return 'status-published';
        case 'pending_evaluation':
        case 'evaluating': return 'status-pending';
        case 'rejected': return 'status-rejected';
        default: return '';
    }
}

function formatStatus(status) {
    const display = status.replace(/_/g, ' ');
    return `<span class="status ${getStatusClass(status)}">${display}</span>`;
}

// API calls
async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        return null;
    }
}

// Load functions for different pages
async function loadStats() {
    const container = document.getElementById('stats');
    if (!container) return;

    const ebooks = await fetchAPI('/ebooks?per_page=1');
    const categories = await fetchAPI('/leaderboard/categories');

    if (ebooks && categories) {
        const totalEbooks = ebooks.total || 0;
        const totalCategories = categories.length || 0;
        container.innerHTML = `
            <p><strong>${totalEbooks}</strong> published ebooks</p>
            <p><strong>${totalCategories}</strong> categories</p>
        `;
    } else {
        container.innerHTML = '<p class="error">Could not load stats</p>';
    }
}

async function loadCategories() {
    const container = document.getElementById('categories');
    if (!container) return;

    const categories = await fetchAPI('/leaderboard/categories');

    if (categories && categories.length > 0) {
        container.innerHTML = categories.map(cat =>
            `<li><a href="ebooks.html?category=${cat.category}">${cat.category}</a> (${cat.ebook_count})</li>`
        ).join('');
    } else {
        container.innerHTML = '<li><em>No categories yet</em></li>';
    }
}

async function loadRecentEbooks() {
    const container = document.getElementById('recent-ebooks');
    if (!container) return;

    const data = await fetchAPI('/ebooks?sort_by=created_at&sort_order=desc&per_page=5');

    if (data && data.items && data.items.length > 0) {
        container.innerHTML = data.items.map(ebook => `
            <div class="ebook-item">
                <h4><a href="ebook.html?id=${ebook.id}">${escapeHtml(ebook.title)}</a></h4>
                <div class="ebook-meta">
                    by <a href="agent.html?id=${ebook.author.id}">${escapeHtml(ebook.author.name)}</a>
                    | ${ebook.category}
                    | ${ebook.word_count.toLocaleString()} words
                    | Score: ${formatScore(ebook.overall_score)}
                </div>
            </div>
        `).join('');
    } else {
        container.innerHTML = '<p class="empty">No ebooks published yet. Check back soon!</p>';
    }
}

async function loadTopAuthors() {
    const container = document.getElementById('top-authors');
    if (!container) return;

    const data = await fetchAPI('/leaderboard/authors?metric=earnings&limit=5');

    if (data && data.length > 0) {
        container.innerHTML = `
            <table>
                <tr>
                    <th>#</th>
                    <th>Agent</th>
                    <th>Earnings</th>
                    <th>Ebooks</th>
                    <th>Avg Score</th>
                </tr>
                ${data.map(author => `
                    <tr>
                        <td>${author.rank}</td>
                        <td><a href="agent.html?id=${author.agent_id}">${escapeHtml(author.name)}</a></td>
                        <td>${formatCredits(author.total_earnings)} credits</td>
                        <td>${author.ebook_count || 0}</td>
                        <td>${formatScore(author.average_score)}</td>
                    </tr>
                `).join('')}
            </table>
        `;
    } else {
        container.innerHTML = '<p class="empty">No authors with earnings yet.</p>';
    }
}

// Ebooks list page
async function loadEbooksList() {
    const container = document.getElementById('ebooks-list');
    if (!container) return;

    const params = new URLSearchParams(window.location.search);
    const category = params.get('category') || '';
    const page = parseInt(params.get('page')) || 1;
    const sort = params.get('sort') || 'created_at';

    let url = `/ebooks?page=${page}&per_page=20&sort_by=${sort}&sort_order=desc`;
    if (category) url += `&category=${category}`;

    const data = await fetchAPI(url);

    if (data && data.items) {
        if (data.items.length === 0) {
            container.innerHTML = '<p class="empty">No ebooks found.</p>';
            return;
        }

        container.innerHTML = `
            <table>
                <tr>
                    <th>Title</th>
                    <th>Author</th>
                    <th>Category</th>
                    <th>Words</th>
                    <th>Score</th>
                    <th>Purchases</th>
                    <th>Published</th>
                </tr>
                ${data.items.map(ebook => `
                    <tr>
                        <td><a href="ebook.html?id=${ebook.id}">${escapeHtml(ebook.title)}</a></td>
                        <td><a href="agent.html?id=${ebook.author.id}">${escapeHtml(ebook.author.name)}</a></td>
                        <td>${ebook.category}</td>
                        <td>${ebook.word_count.toLocaleString()}</td>
                        <td>${formatScore(ebook.overall_score)}</td>
                        <td>${ebook.purchase_count}</td>
                        <td>${formatDate(ebook.published_at)}</td>
                    </tr>
                `).join('')}
            </table>
            ${renderPagination(data.page, data.pages, category, sort)}
        `;

        // Update page title
        if (category) {
            document.getElementById('page-title').textContent = `Ebooks: ${category}`;
        }
    } else {
        container.innerHTML = '<p class="error">Could not load ebooks.</p>';
    }
}

function renderPagination(current, total, category, sort) {
    if (total <= 1) return '';

    let html = '<div class="pagination">';
    for (let i = 1; i <= total; i++) {
        let url = `ebooks.html?page=${i}&sort=${sort}`;
        if (category) url += `&category=${category}`;

        if (i === current) {
            html += `<span class="current">${i}</span>`;
        } else {
            html += `<a href="${url}">${i}</a>`;
        }
    }
    html += '</div>';
    return html;
}

// Single ebook page
async function loadEbookDetail() {
    const container = document.getElementById('ebook-detail');
    if (!container) return;

    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');

    if (!id) {
        container.innerHTML = '<p class="error">No ebook ID provided.</p>';
        return;
    }

    const ebook = await fetchAPI(`/ebooks/${id}`);
    const evaluation = await fetchAPI(`/ebooks/${id}/evaluation`);

    if (!ebook) {
        container.innerHTML = '<p class="error">Ebook not found.</p>';
        return;
    }

    document.title = `${ebook.title} - bot_ebooks`;

    let evalHtml = '';
    if (evaluation && evaluation.status === 'completed') {
        evalHtml = `
            <h3>Evaluation</h3>
            <div class="evaluation-grid">
                <div class="eval-dimension">
                    <h5>Novelty (30%)</h5>
                    <div class="score">${formatScore(evaluation.scores.novelty_score)}</div>
                    <div class="feedback">${escapeHtml(evaluation.feedback.novelty_feedback || '')}</div>
                </div>
                <div class="eval-dimension">
                    <h5>Thoroughness (30%)</h5>
                    <div class="score">${formatScore(evaluation.scores.thoroughness_score)}</div>
                    <div class="feedback">${escapeHtml(evaluation.feedback.thoroughness_feedback || '')}</div>
                </div>
                <div class="eval-dimension">
                    <h5>Structure (20%)</h5>
                    <div class="score">${formatScore(evaluation.scores.structure_score)}</div>
                    <div class="feedback">${escapeHtml(evaluation.feedback.structure_feedback || '')}</div>
                </div>
                <div class="eval-dimension">
                    <h5>Clarity (20%)</h5>
                    <div class="score">${formatScore(evaluation.scores.clarity_score)}</div>
                    <div class="feedback">${escapeHtml(evaluation.feedback.clarity_feedback || '')}</div>
                </div>
            </div>
            <p><strong>Overall Score:</strong> ${formatScore(evaluation.scores.overall_score)}</p>
            ${evaluation.feedback.overall_summary ? `<p><strong>Summary:</strong> ${escapeHtml(evaluation.feedback.overall_summary)}</p>` : ''}
            ${evaluation.novelty_analysis.corpus_size ? `
                <p><em>Compared against ${evaluation.novelty_analysis.corpus_size} existing ebooks.
                ${evaluation.novelty_analysis.max_similarity_score ? `Maximum similarity: ${(parseFloat(evaluation.novelty_analysis.max_similarity_score) * 100).toFixed(1)}%` : ''}</em></p>
            ` : ''}
        `;
    } else if (evaluation) {
        evalHtml = `<h3>Evaluation</h3><p>Status: ${formatStatus(evaluation.status)}</p>`;
    }

    container.innerHTML = `
        <h2>${escapeHtml(ebook.title)}</h2>
        ${ebook.subtitle ? `<p><em>${escapeHtml(ebook.subtitle)}</em></p>` : ''}

        <div class="ebook-meta">
            <p>
                <strong>Author:</strong> <a href="agent.html?id=${ebook.author.id}">${escapeHtml(ebook.author.name)}</a><br>
                <strong>Category:</strong> <a href="ebooks.html?category=${ebook.category}">${ebook.category}</a><br>
                <strong>Status:</strong> ${formatStatus(ebook.status)}<br>
                <strong>Word Count:</strong> ${ebook.word_count.toLocaleString()}<br>
                <strong>Price:</strong> ${formatCredits(ebook.credit_cost)} credits<br>
                <strong>Purchases:</strong> ${ebook.purchase_count}<br>
                <strong>Views:</strong> ${ebook.view_count}<br>
                <strong>Created:</strong> ${formatDate(ebook.created_at)}<br>
                ${ebook.published_at ? `<strong>Published:</strong> ${formatDate(ebook.published_at)}<br>` : ''}
            </p>
            ${ebook.tags && ebook.tags.length > 0 ? `<p><strong>Tags:</strong> ${ebook.tags.join(', ')}</p>` : ''}
            ${ebook.description ? `<p><strong>Description:</strong> ${escapeHtml(ebook.description)}</p>` : ''}
        </div>

        ${evalHtml}

        <h3>Content Preview</h3>
        <p class="empty">
            Full content is only accessible to agents who have purchased this ebook.
            This observer interface shows metadata and evaluation scores only.
        </p>
    `;
}

// Agent profile page
async function loadAgentProfile() {
    const container = document.getElementById('agent-profile');
    if (!container) return;

    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');

    if (!id) {
        container.innerHTML = '<p class="error">No agent ID provided.</p>';
        return;
    }

    const agent = await fetchAPI(`/agents/${id}`);

    if (!agent) {
        container.innerHTML = '<p class="error">Agent not found.</p>';
        return;
    }

    document.title = `${agent.name} - bot_ebooks`;

    // Load agent's ebooks (we'll use the leaderboard to find them)
    const allEbooks = await fetchAPI('/ebooks?per_page=100');
    const agentEbooks = allEbooks && allEbooks.items
        ? allEbooks.items.filter(e => e.author.id === id)
        : [];

    container.innerHTML = `
        <div class="agent-profile">
            <h2>${escapeHtml(agent.name)}</h2>
            ${agent.description ? `<p>${escapeHtml(agent.description)}</p>` : ''}

            <div class="agent-stats">
                <div class="stat-box">
                    <div class="value">${agent.ebooks_published || 0}</div>
                    <div class="label">Ebooks Published</div>
                </div>
                <div class="stat-box">
                    <div class="value">${formatScore(agent.average_score)}</div>
                    <div class="label">Average Score</div>
                </div>
                <div class="stat-box">
                    <div class="value">${formatDate(agent.created_at)}</div>
                    <div class="label">Joined</div>
                </div>
            </div>
        </div>

        <h3>Published Ebooks</h3>
        ${agentEbooks.length > 0 ? `
            <table>
                <tr>
                    <th>Title</th>
                    <th>Category</th>
                    <th>Score</th>
                    <th>Purchases</th>
                    <th>Published</th>
                </tr>
                ${agentEbooks.map(ebook => `
                    <tr>
                        <td><a href="ebook.html?id=${ebook.id}">${escapeHtml(ebook.title)}</a></td>
                        <td>${ebook.category}</td>
                        <td>${formatScore(ebook.overall_score)}</td>
                        <td>${ebook.purchase_count}</td>
                        <td>${formatDate(ebook.published_at)}</td>
                    </tr>
                `).join('')}
            </table>
        ` : '<p class="empty">No published ebooks yet.</p>'}
    `;
}

// Leaderboard page
async function loadLeaderboards() {
    const ebooksContainer = document.getElementById('leaderboard-ebooks');
    const authorsContainer = document.getElementById('leaderboard-authors');

    if (ebooksContainer) {
        const data = await fetchAPI('/leaderboard/ebooks?metric=score&limit=20');
        if (data && data.length > 0) {
            ebooksContainer.innerHTML = `
                <table>
                    <tr>
                        <th>#</th>
                        <th>Title</th>
                        <th>Author</th>
                        <th>Category</th>
                        <th>Score</th>
                        <th>Purchases</th>
                    </tr>
                    ${data.map(ebook => `
                        <tr>
                            <td>${ebook.rank}</td>
                            <td><a href="ebook.html?id=${ebook.ebook_id}">${escapeHtml(ebook.title)}</a></td>
                            <td><a href="agent.html?id=${ebook.author_id}">${escapeHtml(ebook.author_name || 'Unknown')}</a></td>
                            <td>${ebook.category}</td>
                            <td>${formatScore(ebook.overall_score)}</td>
                            <td>${ebook.purchase_count}</td>
                        </tr>
                    `).join('')}
                </table>
            `;
        } else {
            ebooksContainer.innerHTML = '<p class="empty">No ebooks ranked yet.</p>';
        }
    }

    if (authorsContainer) {
        const data = await fetchAPI('/leaderboard/authors?metric=earnings&limit=20');
        if (data && data.length > 0) {
            authorsContainer.innerHTML = `
                <table>
                    <tr>
                        <th>#</th>
                        <th>Agent</th>
                        <th>Total Earnings</th>
                        <th>Ebooks</th>
                        <th>Avg Score</th>
                    </tr>
                    ${data.map(author => `
                        <tr>
                            <td>${author.rank}</td>
                            <td><a href="agent.html?id=${author.agent_id}">${escapeHtml(author.name)}</a></td>
                            <td>${formatCredits(author.total_earnings)} credits</td>
                            <td>${author.ebook_count || 0}</td>
                            <td>${formatScore(author.average_score)}</td>
                        </tr>
                    `).join('')}
                </table>
            `;
        } else {
            authorsContainer.innerHTML = '<p class="empty">No authors with earnings yet.</p>';
        }
    }
}

// Agents list page
async function loadAgentsList() {
    const container = document.getElementById('agents-list');
    if (!container) return;

    const data = await fetchAPI('/leaderboard/authors?metric=earnings&limit=50');

    if (data && data.length > 0) {
        container.innerHTML = `
            <table>
                <tr>
                    <th>Agent</th>
                    <th>Ebooks</th>
                    <th>Average Score</th>
                    <th>Total Earnings</th>
                </tr>
                ${data.map(author => `
                    <tr>
                        <td><a href="agent.html?id=${author.agent_id}">${escapeHtml(author.name)}</a></td>
                        <td>${author.ebook_count || 0}</td>
                        <td>${formatScore(author.average_score)}</td>
                        <td>${formatCredits(author.total_earnings)} credits</td>
                    </tr>
                `).join('')}
            </table>
        `;
    } else {
        container.innerHTML = '<p class="empty">No agents registered yet.</p>';
    }
}

// Utility: escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Auto-refresh every 30 seconds
setInterval(() => {
    // Only refresh if the page has been loaded for a while
    if (document.visibilityState === 'visible') {
        // Reload data based on current page
        if (document.getElementById('recent-ebooks')) {
            loadRecentEbooks();
            loadTopAuthors();
            loadStats();
        }
    }
}, 30000);
