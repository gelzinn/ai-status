.pragma library

// Update keyed rows in place so streaming results never restart animations.
function sync(model, entries, key) {
    entries = entries || []
    for (let index = 0; index < entries.length; index++) {
        const token = key(entries[index])
        let previous = index
        while (previous < model.count && model.get(previous).token !== token) previous++
        if (previous === model.count) model.insert(index, {token: token, entry: JSON.parse(JSON.stringify(entries[index]))})
        else {
            if (previous !== index) model.move(previous, index, 1)
            if (JSON.stringify(model.get(index).entry) !== JSON.stringify(entries[index]))
                model.setProperty(index, "entry", JSON.parse(JSON.stringify(entries[index])))
        }
    }
    if (model.count > entries.length) model.remove(entries.length, model.count - entries.length)
}
