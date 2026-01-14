const express = require('express')
const fs = require('fs')
const OSS = require('ali-oss')
const configObj = JSON.parse(fs.readFileSync('./config.json'))

const ossClient = new OSS({
    region: configObj.region,
    accessKeyId: configObj.APIKey,
    accessKeySecret: configObj.APIPassword,
    bucket: configObj.bucket
})

async function getRandomEnglishName() {
    let result = []
    try {
        result = (await ossClient.listV2({
            'prefix': configObj.enFolder,
            'max-keys': 100
        })).objects
    } catch (err) {
        console.log(err)
    }
    const len = result.length
    const randomNumber = Math.floor(Math.random() * len)
    return result[randomNumber]
}

async function getEnglishImage(fileName) {
    try {
        image = (await ossClient.get(fileName)).content
    } catch (err) {
        console.log(err)
    }
}

const expressApp = express()

expressApp.get('/random-english', async (req, res) => {
    try {
        const fileName = await getRandomEnglishName()
        res.send({ fileName })   // 返回 JSON 给前端
    } catch (e) {
        res.status(500).send({ error: 'OSS error' + e })
    }
})

expressApp.listen(configObj.port, () => {
    console.log(`Example app listening on port ${configObj.port}`)
})