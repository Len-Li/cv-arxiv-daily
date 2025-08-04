// 自定义JavaScript功能

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 添加搜索功能
    addSearchFunction();
    
    // 添加排序功能
    addSortFunction();
    
    // 添加平滑滚动
    addSmoothScroll();
    
    // 添加返回顶部按钮
    addBackToTopButton();
    
    // 添加表格行点击高亮
    addTableRowHighlight();
});

// 搜索功能
function addSearchFunction() {
    // 创建搜索框
    const searchContainer = document.createElement('div');
    searchContainer.className = 'search-container';
    searchContainer.innerHTML = `
        <input type="text" id="searchInput" class="search-input" placeholder="搜索论文标题...">
        <button onclick="clearSearch()" style="margin-left: 10px; padding: 12px 20px; background: #667eea; color: white; border: none; border-radius: 25px; cursor: pointer;">清除</button>
    `;
    
    // 插入到页面开头
    const firstHeading = document.querySelector('h1') || document.querySelector('h2');
    if (firstHeading) {
        firstHeading.parentNode.insertBefore(searchContainer, firstHeading.nextSibling);
    }
    
    // 添加搜索事件监听
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', function() {
        searchPapers();
    });
}

// 搜索论文
function searchPapers() {
    const input = document.getElementById('searchInput');
    const filter = input.value.toLowerCase();
    const tables = document.querySelectorAll('table');
    
    tables.forEach(table => {
        const rows = table.getElementsByTagName('tr');
        
        for (let i = 1; i < rows.length; i++) {
            const titleCell = rows[i].cells[1]; // 标题列
            if (titleCell) {
                const title = titleCell.textContent.toLowerCase();
                if (title.includes(filter)) {
                    rows[i].style.display = '';
                } else {
                    rows[i].style.display = 'none';
                }
            }
        }
    });
}

// 清除搜索
function clearSearch() {
    const input = document.getElementById('searchInput');
    input.value = '';
    searchPapers();
}

// 排序功能
function addSortFunction() {
    const tables = document.querySelectorAll('table');
    
    tables.forEach(table => {
        const headers = table.querySelectorAll('th');
        headers.forEach((header, index) => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', () => sortTable(table, index));
            header.title = '点击排序';
        });
    });
}

// 排序表格
function sortTable(table, columnIndex) {
    const tbody = table.querySelector('tbody');
    if (!tbody) return;
    
    const rows = Array.from(tbody.getElementsByTagName('tr'));
    
    rows.sort((a, b) => {
        const aText = a.cells[columnIndex]?.textContent || '';
        const bText = b.cells[columnIndex]?.textContent || '';
        return aText.localeCompare(bText);
    });
    
    rows.forEach(row => tbody.appendChild(row));
}

// 平滑滚动
function addSmoothScroll() {
    const links = document.querySelectorAll('a[href^="#"]');
    
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);
            
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// 返回顶部按钮
function addBackToTopButton() {
    const button = document.createElement('button');
    button.innerHTML = '↑';
    button.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 50px;
        height: 50px;
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        border: none;
        border-radius: 50%;
        font-size: 20px;
        cursor: pointer;
        display: none;
        z-index: 1000;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    `;
    
    document.body.appendChild(button);
    
    // 显示/隐藏按钮
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            button.style.display = 'block';
        } else {
            button.style.display = 'none';
        }
    });
    
    // 点击返回顶部
    button.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

// 表格行高亮
function addTableRowHighlight() {
    const tables = document.querySelectorAll('table');
    
    tables.forEach(table => {
        const rows = table.querySelectorAll('tr');
        rows.forEach(row => {
            row.addEventListener('mouseenter', function() {
                this.style.backgroundColor = '#f8f9fa';
            });
            
            row.addEventListener('mouseleave', function() {
                this.style.backgroundColor = '';
            });
        });
    });
}

// 添加复制链接功能
function addCopyLinkFunction() {
    const links = document.querySelectorAll('a[href*="arxiv.org"]');
    
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            // 添加点击反馈
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });
}

// 添加统计信息
function addStatistics() {
    const tables = document.querySelectorAll('table');
    let totalPapers = 0;
    
    tables.forEach(table => {
        const rows = table.querySelectorAll('tr');
        totalPapers += rows.length - 1; // 减去表头
    });
    
    const statsDiv = document.createElement('div');
    statsDiv.style.cssText = `
        text-align: center;
        margin: 20px 0;
        padding: 15px;
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        border-radius: 10px;
        font-weight: bold;
    `;
    statsDiv.innerHTML = `📊 总共 ${totalPapers} 篇论文`;
    
    const firstHeading = document.querySelector('h1') || document.querySelector('h2');
    if (firstHeading) {
        firstHeading.parentNode.insertBefore(statsDiv, firstHeading.nextSibling);
    }
}

// 初始化统计信息
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(addStatistics, 1000); // 延迟加载统计信息
    addCopyLinkFunction();
}); 