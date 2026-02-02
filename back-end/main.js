const express = require('express')
const fs = require('fs')
const OSS = require('ali-oss')
const cors = require('cors')
const configObj = JSON.parse(fs.readFileSync('./config.dev.json'))

const ossClient = new OSS({
    region: configObj.region,
    accessKeyId: configObj.APIKey,
    accessKeySecret: configObj.APIPassword,
    bucket: configObj.bucket
})

async function getRandomChineseName() {
    let result = []
    try {
        result = (await ossClient.listV2({
            'prefix': configObj.zhFolder,
            'max-keys': 100
        })).objects
    } catch (err) {
        console.log(err)
    }
    const len = result.length
    const randomNumber = Math.floor(Math.random() * len)
    const resultName = result[randomNumber].name.replace(configObj.zhFolder+'/','').replace('.jpg','')
    return resultName
}

async function getImageByName(isChinese,fileName) {
    const folderName = isChinese? configObj.zhFolder : configObj.enFolder
    const fullName = folderName +'/'+ fileName +'.jpg'
    try {
        const image = (await ossClient.get(fullName)).content
        return image
    } catch (err) {
        console.log(err)
    }
}


const expressApp = express()
expressApp.use(cors())

expressApp.get('/random-name', async (req, res) => {
    try {
        const name  = await getRandomChineseName()
        res.send(name)   // 返回 JSON 给前端
    } catch (e) {
        res.status(500).send({ error: 'OSS error' + e })
    }
})

expressApp.get('/chinese',async (req,res)=>{
    try {
        const image  = await getImageByName(true,req.query.name)
        res.set('Content-Type', 'image/jpeg');
        res.send(image)
    } catch(e){
        console.log(e)
    }
})

expressApp.get('/english',async (req,res)=>{
    try {
        const image  = await getImageByName(false,req.query.name)
        res.set('Content-Type', 'image/jpeg');
        res.send(image)
    } catch(e){
        console.log(e)
    }
})

expressApp.listen(configObj.port, () => {
    console.log(`Example app listening on port ${configObj.port}`)
})