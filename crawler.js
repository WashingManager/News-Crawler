const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const { getKeywords } = require('./keyword.js');

const URL = 'https://news.daum.net/global?nil_profile=mini&nil_src=news';

async function crawlNews() {
  try {
    let existingNews = [];
    if (fs.existsSync('news.json')) {
      existingNews = JSON.parse(fs.readFileSync('news.json', 'utf8'));
    }

    const keywords = getKeywords();
    const response = await axios.get(URL);
    const $ = cheerio.load(response.data);

    const newsItems = [];
    $('.list_newsheadline2 .item_newsheadline2, .list_newsbasic .item_newsbasic').each((i, elem) => {
      const title = $(elem).find('.tit_txt').text().trim();
      const link = $(elem).attr('href');
      const time = $(elem).find('.txt_info').last().text().trim();

      if (keywords.some(keyword => title.includes(keyword))) {
        newsItems.push({ title, time, link });
      }
    });

    const newNews = newsItems.filter(item => 
      !existingNews.some(existing => existing.link === item.link)
    );

    const updatedNews = [...newNews, ...existingNews].slice(0, 50);
    fs.writeFileSync('news.json', JSON.stringify(updatedNews, null, 2));
    console.log(`News updated successfully: ${newNews.length} new items added`);
  } catch (error) {
    console.error('Error crawling news:', error);
  }
}

crawlNews();
