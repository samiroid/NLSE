#!/usr/bin/python
'''
Sub-space training 
'''
import sys
sys.path.append('code')

import cPickle
import FMeasure as Fmes
from ipdb import set_trace
import nlse
import numpy as np
import theano
import theano.tensor as T

####################################
#           CONFIG 
####################################
    
# TRAIN 
n_iter  = 5
lrate   = np.array(0.01).astype(theano.config.floatX)
# Pre-trained embeddings
pretrained_emb = 'data/pkl/Emb.pkl'
# Sub space size 
sub_size = 10

def main(train_data, dev_data, model_path):

    ####################################
    #   LOAD TRAIN/DEV DATA 
    ####################################    
    print "Training data: %s\nDev data: %s " % (train_data, dev_data)
    print "Model: %s" % model_path
    with open(train_data, 'rb') as fid:
        train_x, train_y = cPickle.load(fid) 
    with open(dev_data, 'rb') as fid:
        dev_x, dev_y = cPickle.load(fid) 

    # RESHAPE TRAIN DATA AS A SINGLE NUMPY ARRAY
    # Start and end indices    
    lens = np.array([len(tr) for tr in train_x]).astype('int32')
    st   = np.cumsum(np.concatenate((np.zeros((1, )), lens[:-1]), 0)).astype('int32')
    ed   = (st + lens).astype('int32')
    x    = np.zeros((ed[-1], 1))
    for i, ins_x in enumerate(train_x):        
        x[st[i]:ed[i]] = ins_x[:, None].astype('int32')         

    #reformat the labelset 
    train_y = [np.array(dy).astype('int32')[None] for dy in train_y]
    dev_y = [np.array(dy).astype('int32')[None] for dy in dev_y]

    # Train data and instance start and ends
    x  = theano.shared(x.astype('int32'), borrow=True) 
    y  = theano.shared(np.array(train_y).astype('int32'), borrow=True)
    st = theano.shared(st, borrow=True)
    ed = theano.shared(ed, borrow=True)    

    ####################################
    #           NLSE Model
    #################################### 
    nn = nlse.NLSE(pretrained_emb, sub_size=sub_size)
    # Update rule
    updates = [(pr, pr-lrate*gr) for pr, gr in zip(nn.params, nn.nablas)]
    # Mini-batch
    i  = T.lscalar()
    givens={ nn.z0 : x[st[i]:ed[i], 0],
             nn.y  : y[i] }
    train_batch = theano.function(inputs=[i], outputs=nn.F, updates=updates, givens=givens)

    ####################################
    #           TRAINING    
    #################################### 
    last_cr  = None
    best_cr  = [0, 0]
    for i in np.arange(n_iter):
        # Training Epoch                         
        p_train = 0 
        for j in np.arange(len(train_x)).astype('int32'): 
            p_train += train_batch(j)             
            # INFO
            if not (j % 100):
                sys.stdout.write("\rTraining %d/%d" % (j+1, len(train_x)))
                sys.stdout.flush()   

        # Evaluation
        cr      = 0.
        mapp    = np.array([ 1, 2, 0])
        ConfMat = np.zeros((3, 3))
        for j, x, y in zip(np.arange(len(dev_x)), dev_x, dev_y):
            # Prediction
            p_y   = nn.forward(x)
            hat_y = np.argmax(p_y)
            # Confusion matrix
            ConfMat[mapp[y[0]], mapp[hat_y]] += 1
            # Accuracy
            cr    = (cr*j + (hat_y == y[0]).astype(float))/(j+1)
            # INFO
            sys.stdout.write("\rDevel %d/%d            " % (j+1, len(dev_x)))
            sys.stdout.flush()   
        # Compute SemEval scores
        Fm = Fmes.FmesSemEval(confusionMatrix=ConfMat)        
        # INFO
        if last_cr:
            # Keep the best model
            if best_cr[0] < cr:
                best_cr = [cr, i+1]
            delta_cr = cr - last_cr
            if delta_cr >= 0:
                print ("\rEpoch %2d/%2d: Acc %2.5f%% \033[32m+%2.5f\033[0m (Fm %2.5f%%)" % 
                       (i+1, n_iter, cr*100, delta_cr*100, Fm*100))
            else: 
                print ("\rEpoch %2d/%2d: Acc %2.5f%% \033[31m%2.5f\033[0m (Fm %2.5f%%)" % 
                       (i+1, n_iter, cr*100, delta_cr*100, Fm*100))
        else:
            print "\rEpoch %2d/%2d: %2.5f (Fm %2.5f%%)" % (i+1, n_iter, cr*100,
                                                           Fm*100)
            best_cr = [cr, i+1]
        last_cr = cr

    # SAVE MODEL    
    nn.save(model_path)

if __name__ == '__main__':
    MESSAGE = "python code/train.py train_file dev_file model_path"
    
    try:
        train_feats = sys.argv[1]
        dev_feats   = sys.argv[2]
        model_path  = sys.argv[3]
        main(train_feats, dev_feats, model_path)
    except IndexError:
        print "ERROR: missing files"
        print MESSAGE    
    
